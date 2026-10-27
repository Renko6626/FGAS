"""Shared low/high business reads. Query conditions never confer authorization."""
from datetime import datetime, timedelta, timezone
from backend.application.agent_access import AgentAccess
from backend.application import directory_views, funds, warehouse, warehouse_catalogs, stocktakes, settlements
from backend.infrastructure import store, stock_store, agent_store
from backend.infrastructure.models import Transfer, StockTransfer
from backend.kernel.accounting import DomainError


def minor_to_yuan(value: int) -> str:
    whole, fraction = divmod(abs(value), 100)
    return f'{"-" if value < 0 else ""}{whole}.{fraction:02d}'


def money(value):
    """Add refillable amounts, including nested settlement and journal results."""
    if isinstance(value, list):
        return [money(item) for item in value]
    if isinstance(value, dict):
        result = {key: money(item) for key, item in value.items()}
        for key, item in value.items():
            if key.endswith('_minor') and isinstance(item, int):
                result[key[:-6]] = minor_to_yuan(item)
        return result
    return value


DEFAULT_WINDOW = timedelta(days=30)
TIME_KEYS = ('created_at_from', 'created_at_to', 'posted_at_from', 'posted_at_to', 'as_of')


def _filters(filters):
    result = {key: value for key, value in (filters or {}).items() if value is not None}
    result.setdefault('page', 1)
    result.setdefault('limit', 20)
    if not isinstance(result['page'], int) or result['page'] < 1 or not isinstance(result['limit'], int) or not 1 <= result['limit'] <= 100:
        raise DomainError('page 须大于零，limit 须为 1 至 100')
    for key in TIME_KEYS:
        if key in result:
            value = result[key]
            try:
                parsed = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
                if parsed.tzinfo is None or parsed.utcoffset() is None:
                    raise ValueError()
            except (ValueError, AttributeError, TypeError):
                raise DomainError('时间必须是带时区的 ISO 时间')
            result[key] = parsed
    if result.get('basis') not in (None, 'posted', 'effective_date'):
        raise DomainError('as-of 基准无效')
    return result


def _event_filters(filters):
    """Default recent event lists; explicit time conditions or all_time opt out."""
    result = _filters(filters)
    explicit_time = any(key.startswith(('created_at_', 'effective_date_', 'posted_at_')) for key in result)
    if not result.get('all_time') and not explicit_time:
        result['created_at_from'] = datetime.now(timezone.utc) - DEFAULT_WINDOW
    return result


def _result(data):
    return dict(api_version='2', data=money(data))


def _page(rows, filters, *, sliced=False, snapshot_at=None, **extra):
    start = 0 if sliced else (filters['page'] - 1) * filters['limit']
    selected = rows[start:start + filters['limit'] + 1]
    return _result(dict(items=selected[:filters['limit']], page=filters['page'], has_more=len(selected) > filters['limit'], filters=filters, snapshot_at=snapshot_at or datetime.now(timezone.utc), **extra))


def _database_page(value, filters, **extra):
    return _result(dict(items=value['items'], page=filters['page'],
                        has_more=filters['page'] * filters['limit'] < value['total'],
                        filters=filters, snapshot_at=value['snapshot_at'], **extra))


def _accounts(db, filters, stock=False):
    getter = store.stock_accounts if stock else store.accounts
    result = []
    for item in getter(db, filters.get('tag'), filters.get('kind'), filters.get('member_id')):
        if filters.get('q') is not None and filters['q'].casefold() not in item.name.casefold(): continue
        if 'active' in filters and item.active != filters['active']: continue
        row = directory_views.account_view(db, item, stock=stock)
        result.append(row)
    return sorted(result, key=lambda row: (row['name'], row['id']))


def me(db, access: AgentAccess, filters: dict) -> dict:
    return _result(dict(user=dict(display_name=access.user.display_name, role=access.user.role),
                        connection=dict(name=access.credential_name, level=access.level)))


def list_fund_accounts(db, access: AgentAccess, filters: dict) -> dict:
    filters = _filters(filters)
    return _page(_accounts(db, filters), filters)


def list_stock_accounts(db, access: AgentAccess, filters: dict) -> dict:
    filters = _filters(filters)
    return _page(_accounts(db, filters, True), filters)


def get_stock_account(db, access: AgentAccess, identifier: str) -> dict:
    return _result(warehouse_catalogs.account_detail(db, identifier))


def list_skus(db, access: AgentAccess, filters: dict) -> dict:
    filters = _filters(filters)
    rows = warehouse_catalogs.skus(db, **{key: filters[key] for key in ('code','q','tag','active') if key in filters})
    return _page(rows, filters)


def list_members(db, access: AgentAccess, filters: dict) -> dict:
    filters = _filters(filters)
    return _page([directory_views.member_view(item) for item in store.members(db) if 'q' not in filters or filters['q'].casefold() in item.name.casefold()], filters)


def get_fund_balances(db, access: AgentAccess, filters: dict) -> dict:
    filters = _filters(filters)
    as_of = filters.get('as_of')
    basis = filters.get('basis', 'posted')
    rows = _accounts(db, filters)
    if filters.get('account_id') is not None:
        rows = [row for row in rows if row['id'] == filters['account_id']]
    for row in rows:
        row['balance_minor'] = funds.balance(db, store.get_account(db, row['id']), as_of=as_of, basis=basis)
    # Existing summary means the public funds total, even when private rows are read.
    summary = funds.summary(db, as_of=as_of, basis=basis)
    return _page(rows, filters, total_minor=summary['total_minor'], currency='CNY',
                 as_of=as_of, basis=basis if as_of is not None else None)


def _stock_view(db, item, detail=False):
    return warehouse.transfer_view(db, item, detail=detail)


def _transfers(db, access, filters, stock=False):
    filters = _event_filters(filters)
    filters.setdefault('submitted_by_current_connection', False)
    rows = agent_store.transfer_page(db, StockTransfer if stock else Transfer,
                                    warehouse_catalogs.sku_filters(db, filters) if stock else filters,
                                    access.credential_id)
    return _page([_stock_view(db, row) if stock else funds.transfer_view(db, row) for row in rows], filters, sliced=True)


def list_fund_transfers(db, access: AgentAccess, filters: dict) -> dict:
    return _transfers(db, access, filters)


def list_stock_transfers(db, access: AgentAccess, filters: dict) -> dict:
    return _transfers(db, access, filters, True)


def get_fund_transfer(db, access: AgentAccess, identifier: str) -> dict:
    return _result(funds.transfer_view(db, funds.get_transfer(db, identifier), True))


def get_stock_transfer(db, access: AgentAccess, identifier: str) -> dict:
    return _result(warehouse.transfer_detail(db, identifier))


def get_inventory(db, access: AgentAccess, filters: dict) -> dict:
    filters = _filters(filters)
    as_of = filters.get('as_of')
    basis = filters.get('basis', 'posted')
    value = warehouse.inventory(db, {key: filters[key] for key in ('account_id','sku_code','member_id','as_of','basis') if key in filters},
                                page=filters['page'], limit=filters['limit'])
    return _database_page(value, filters, totals=value['totals'],
                 as_of=as_of, basis=basis if as_of is not None else None)


def list_stock_moves(db, access: AgentAccess, filters: dict) -> dict:
    filters = _event_filters(filters)
    value = warehouse.list_moves_page(db, {key: filters[key] for key in ('transfer_id','sku_code','source_account_id','destination_account_id','effective_date_from','effective_date_to','created_at_from','created_at_to','posted_at_from','posted_at_to') if key in filters},
                                      page=filters['page'], limit=filters['limit'], descending=True)
    return _database_page(value, filters)


def get_settlement_overview(db, access: AgentAccess, filters: dict) -> dict:
    return _result(settlements.overview(db, filters['account_id']))


def list_settlement_outstanding(db, access: AgentAccess, filters: dict) -> dict:
    filters = _filters(filters)
    value = settlements.outstanding(db, **filters)
    return _database_page(value, filters, total=value['total'], limit=value['limit'])


def _stocktakes(db, filters, kind):
    filters = _filters(filters)
    rows = stocktakes.list_stocktakes(db, kind, filters.get('status'))
    rows.sort(key=lambda row: (row['created_at'], row['id']), reverse=True)
    return _page(rows, filters)


def list_fund_stocktakes(db, access: AgentAccess, filters: dict) -> dict:
    return _stocktakes(db, filters, 'fund')


def list_stock_stocktakes(db, access: AgentAccess, filters: dict) -> dict:
    return _stocktakes(db, filters, 'stock')


def get_fund_stocktake(db, access: AgentAccess, identifier: str) -> dict:
    return _result(stocktakes.get_stocktake(db, 'fund', identifier))


def get_stock_stocktake(db, access: AgentAccess, identifier: str) -> dict:
    value = stocktakes.get_stocktake(db, 'stock', identifier)
    for row in value['transfers']:
        for key in ('audit','confirmations','related_transfers','fund_references'):
            row.pop(key, None)
    return _result(value)

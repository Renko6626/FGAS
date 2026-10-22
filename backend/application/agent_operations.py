"""Explicit Agent writes over the existing business services."""
from backend.application import catalogs, funds, members, settlements, stock_workflows, stocktakes, warehouse, warehouse_catalogs
from backend.application.agent_access import AgentAccess, require_high
from backend.application.agent_queries import money


def _result(data):
    return dict(api_version='2', data=money(data))


def _resource(resource_type, identifier_key, value, *, applied=False, pending=False):
    return dict(resource_type=resource_type, **{identifier_key: value['id']},
                status=value['status'], ledger_effect_applied=applied, approval_required=pending)


def _fund(db, item, *, applied=False):
    value = funds.transfer_view(db, item) if not isinstance(item, dict) else item
    return _result(_resource('fund_transfer', 'transfer_id', value, applied=applied, pending=value['status']=='pending'))


def _stock(value):
    return _result(_resource('stock_transfer', 'stock_transfer_id', value, pending=value['status']=='pending'))


def _completion(value, confirmation_id, *, applied=False):
    confirmation = next(row for row in value['confirmations'] if row['id'] == confirmation_id)
    return _result(dict(resource_type='stock_confirmation', confirmation_id=confirmation_id,
                        stock_transfer_id=value['id'], status=confirmation['status'],
                        stock_transfer_status=value['status'], ledger_effect_applied=applied,
                        approval_required=confirmation['status']=='pending'))


def _saved(resource_type, identifier_key, value):
    status = value.get('status', 'active' if value.get('active', True) else 'inactive')
    return _result(dict(resource_type=resource_type, **{identifier_key: value['id']}, status=status,
                        ledger_effect_applied=False, approval_required=False, object=value))


def propose_fund_transfer(db, access: AgentAccess, data: dict) -> dict:
    value = funds.submit(db, access.user, data, access=access, submit_mode='propose')
    return _fund(db, value)


def create_fund_transfer(db, access: AgentAccess, data: dict) -> dict:
    require_high(access)
    value = funds.submit(db, access.user, data, access=access, submit_mode='direct')
    return _fund(db, value, applied=True)


def propose_stock_transfer(db, access: AgentAccess, data: dict) -> dict:
    value = warehouse.submit_transfer(db, access.user, data, access=access, submit_mode='propose')
    return _stock(value)


def create_stock_transfer(db, access: AgentAccess, data: dict) -> dict:
    require_high(access)
    value = warehouse.submit_transfer(db, access.user, data, access=access, submit_mode='direct')
    return _stock(value)


def propose_stock_completion(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    value = warehouse.request_completion(db, access.user, identifier, data, access=access, submit_mode='propose')
    return _completion(value, value['confirmation_id'])


def complete_stock_transfer(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = warehouse.request_completion(db, access.user, identifier, data, access=access, submit_mode='direct')
    return _completion(value, value['confirmation_id'], applied=True)


def create_fund_account(db, access: AgentAccess, data: dict) -> dict:
    require_high(access)
    value = catalogs.create_account(db, access.user, data)
    return _saved('fund_account', 'account_id', value)


def update_fund_account(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = catalogs.update_account(db, access.user, identifier, data)
    return _saved('fund_account', 'account_id', value)


def create_stock_account(db, access: AgentAccess, data: dict) -> dict:
    require_high(access)
    value = catalogs.create_stock_account(db, access.user, data)
    return _saved('stock_account', 'account_id', value)


def update_stock_account(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = catalogs.update_stock_account(db, access.user, identifier, data)
    return _saved('stock_account', 'account_id', value)


def create_sku(db, access: AgentAccess, data: dict) -> dict:
    require_high(access)
    value = warehouse_catalogs.create_sku(db, access.user, data)
    return _saved('sku', 'sku_id', value)


def update_sku(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = warehouse_catalogs.update_sku(db, access.user, identifier, data)
    return _saved('sku', 'sku_id', value)


def create_member(db, access: AgentAccess, data: dict) -> dict:
    require_high(access)
    value = members.create_member(db, access.user, data)
    return _saved('member', 'member_id', value)


def update_member(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = members.update_member(db, access.user, identifier, data)
    return _saved('member', 'member_id', value)


def set_stock_custody(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = warehouse_catalogs.set_custody(db, access.user, identifier, data['member_id'])
    return _saved('stock_account', 'account_id', value)


def approve_fund_transfer(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = funds.decide(db, access.user, identifier, data['expected_version'], access=access)
    return _fund(db, value, applied=True)


def reject_fund_transfer(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = funds.decide(db, access.user, identifier, data['expected_version'], data['reason'], access=access)
    return _fund(db, value)


def reverse_fund_transfer(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = funds.reverse(db, access.user, identifier, data['reason'], access=access)
    return _fund(db, value, applied=True)


def approve_stock_transfer(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = warehouse.decide_transfer(db, access.user, identifier, data, access=access)
    return _stock(value)


def reject_stock_transfer(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = warehouse.decide_transfer(db, access.user, identifier, data, rejection=True, access=access)
    return _stock(value)


def cancel_stock_transfer(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = warehouse.cancel_transfer(db, access.user, identifier, data, access=access)
    return _stock(value)


def approve_stock_completion(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = warehouse.decide_completion(db, access.user, identifier, data, access=access)
    return _completion(value, identifier, applied=True)


def reject_stock_completion(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = warehouse.decide_completion(db, access.user, identifier, data, rejection=True, access=access)
    return _completion(value, identifier)


def add_stock_fund_reference(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = warehouse.add_fund_reference(db, access.user, identifier, data, access=access)
    return _result(_resource('stock_transfer', 'stock_transfer_id', value))


def create_settlement(db, access: AgentAccess, data: dict) -> dict:
    require_high(access)
    value = settlements.create(db, access.user, data, access=access)
    return _result(_resource('settlement', 'transfer_id', value['transfer'], applied=True) | dict(matches=value['matches']))


def add_settlement_matches(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = settlements.add_matches(db, access.user, identifier, data['allocations'], access=access)
    return _result(_resource('settlement', 'transfer_id', value['transfer']) | dict(matches=value['matches']))


def create_stock_operation(db, access: AgentAccess, data: dict) -> dict:
    require_high(access)
    value = stock_workflows.submit_stock_with_money(db, access.user, data, access=access)
    fund = _resource('fund_transfer', 'transfer_id', value['fund_transfer'], applied=True)
    stock = _resource('stock_transfer', 'stock_transfer_id', value['stock_transfer'])
    return _result(dict(resource_type='stock_operation', fund_transfer=fund, stock_transfer=stock))


def create_fund_stocktake(db, access: AgentAccess, data: dict) -> dict:
    require_high(access)
    value = stocktakes.create_stocktake(db, access.user, 'fund', data)
    return _saved('fund_stocktake', 'stocktake_id', value)


def update_fund_stocktake(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = stocktakes.update_description(db, access.user, 'fund', identifier, data['description'])
    return _saved('fund_stocktake', 'stocktake_id', value)


def end_fund_stocktake(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = stocktakes.end_stocktake(db, access.user, 'fund', identifier)
    return _saved('fund_stocktake', 'stocktake_id', value)


def create_stock_stocktake(db, access: AgentAccess, data: dict) -> dict:
    require_high(access)
    value = stocktakes.create_stocktake(db, access.user, 'stock', data)
    return _saved('stock_stocktake', 'stocktake_id', value)


def update_stock_stocktake(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = stocktakes.update_description(db, access.user, 'stock', identifier, data['description'])
    return _saved('stock_stocktake', 'stocktake_id', value)


def end_stock_stocktake(db, access: AgentAccess, identifier: str, data: dict) -> dict:
    require_high(access)
    value = stocktakes.end_stocktake(db, access.user, 'stock', identifier)
    return _saved('stock_stocktake', 'stocktake_id', value)


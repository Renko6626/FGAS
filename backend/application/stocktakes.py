"""Stocktakes organize ordinary Transfers through dedicated endpoints."""
from backend.infrastructure import store, stocktake_store
from backend.application import catalogs, funds, warehouse
from backend.application.identity import authorize_write
from backend.kernel.accounting import DomainError


def stocktake_view(db, kind, item):
    endpoint = 'account'
    value = {key: getattr(item, key) for key in ('id', 'name', 'description', 'status', 'created_by', 'created_at')}
    getter = store.get_account if kind == 'fund' else store.get_stock_account
    for side in ('gain', 'loss'):
        key = side + '_' + endpoint + '_id'
        value[key] = getattr(item, key)
        value[side + '_' + endpoint + '_name'] = getter(db, value[key]).name
    return value

def list_stocktakes(db, kind, status=None):
    return [stocktake_view(db, kind, item) for item in stocktake_store.stocktakes(db, kind, status)]

def list_stocktakes_page(db, kind, status=None, q=None, page=1, limit=20):
    items, total = stocktake_store.stocktakes_page(db, kind, status, q=q, page=page, limit=limit)
    return dict(items=[stocktake_view(db, kind, item) for item in items], total=total, page=page, limit=limit)

def require_stocktake(db, kind, identifier):
    item = stocktake_store.get(db, kind, identifier)
    if item is None: raise DomainError('盘点不存在', 404)
    return item

def create_stocktake(db, user, kind, data):
    authorize_write(db, user)
    name = data['name'].strip()
    if not name: raise DomainError('盘点名称不能为空')
    endpoints = {}
    endpoint = 'account'
    for side, label in (('gain', '盘盈'), ('loss', '盘亏')):
        if kind == 'fund':
            value = catalogs.create_account(db, user, dict(name=f'{name}（资金{label}）', kind='external', tags=[label]))
        else:
            value = catalogs.create_stock_account(db, user, dict(name=f'{name}（货物{label}）', tags=[label], kind='external', active=True))
        endpoints[side + '_' + endpoint + '_id'] = value['id']
    item = stocktake_store.create(db, kind, dict(name=name, description=data.get('description', ''), created_by=user.id, **endpoints))
    return stocktake_view(db, kind, item)

def get_stocktake(db, kind, identifier):
    with store.read_snapshot(db) as snapshot:
        item = require_stocktake(snapshot, kind, identifier)
        timestamp = store.snapshot_timestamp(snapshot)
        view = funds.transfer_view if kind == 'fund' else warehouse.transfer_view
        transfers = [view(snapshot, transfer) for transfer in stocktake_store.transfers(snapshot, kind, item)]
        if kind == 'stock': transfers = [value | dict(snapshot_at=timestamp) for value in transfers]
        return dict(stocktake=stocktake_view(snapshot, kind, item), transfers=transfers)

def update_description(db, user, kind, identifier, description):
    authorize_write(db, user)
    item = require_stocktake(db, kind, identifier)
    store.refresh(db, item)
    item.description = description
    db.flush()
    return stocktake_view(db, kind, item)

def end_stocktake(db, user, kind, identifier):
    authorize_write(db, user)
    item = require_stocktake(db, kind, identifier)
    store.refresh(db, item)
    item.status = 'ended'
    db.flush()
    return stocktake_view(db, kind, item)

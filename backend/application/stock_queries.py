"""Inventory query conditions and user-facing quantity formatting."""
from backend.infrastructure import inventory_queries, store, stock_store
from backend.kernel.stock import quantity_string
from backend.application import warehouse_catalogs

def inventory(db,filters=None,page=1,limit=20):
    filters = warehouse_catalogs.sku_filters(db, filters)
    as_of = filters.get('as_of')
    basis = filters.get('basis', 'posted')
    as_of_ts = as_of if as_of is not None and basis == 'posted' else None
    as_of_date = as_of.date() if as_of is not None and basis == 'effective_date' else None
    params = {key:filters.get(key) for key in ('account_id','sku_id','member_id')}
    params.update(as_of_ts=as_of_ts, as_of_date=as_of_date)
    result = inventory_queries.inventory_page(db, params, page=page, limit=limit)
    quantities = []
    for row in result['items']:
        value = dict(row)
        value.pop('snapshot_at')
        value['account_code'] = store.get_stock_account(db,value.pop('account_id')).code
        member_id = value.pop('member_id')
        value['member_code'] = store.get_member(db,member_id).code if member_id else None
        value.pop('sku_id')
        value['quantity'] = quantity_string(int(value['quantity']))
        for field in ('incoming_planned_quantity', 'outgoing_planned_quantity'):
            if value[field] is not None:
                value[field] = quantity_string(int(value[field]))
        value['valuation'] = '未估值'
        quantities.append(value)
    totals = []
    for row in result['totals']:
        value = dict(row)
        value.pop('sku_id')
        for field in ('quantity', 'incoming_to_org_quantity', 'outgoing_from_org_quantity', 'internal_transfer_quantity'):
            if value[field] is not None:
                value[field] = quantity_string(int(value[field]))
        value['valuation'] = '未估值'
        totals.append(value)
    return dict(items=quantities,total=result['total'],page=page,limit=limit,snapshot_at=result['snapshot_at'],
                totals=totals,
                as_of=as_of,basis=basis if as_of is not None else None)

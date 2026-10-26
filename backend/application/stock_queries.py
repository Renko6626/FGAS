"""Inventory query conditions and user-facing quantity formatting."""
from backend.infrastructure import inventory_queries
from backend.kernel.stock import quantity_string

def inventory(db,filters=None,page=1,limit=20):
    filters = filters or {}
    as_of = filters.get('as_of')
    basis = filters.get('basis', 'posted')
    as_of_ts = as_of if as_of is not None and basis == 'posted' else None
    as_of_date = as_of.date() if as_of is not None and basis == 'effective_date' else None
    params = {key:filters.get(key) for key in ('account_id','sku_id','member_id')}
    params.update(as_of_ts=as_of_ts, as_of_date=as_of_date)
    result = inventory_queries.inventory_page(db, params, page=page, limit=limit)
    totals = {}
    for row in result['totals']:
        totals[row['sku_id']] = quantity_string(int(row['quantity']))
    quantities = []
    for row in result['items']:
        value = dict(row)
        value.pop('snapshot_at')
        value['quantity'] = quantity_string(int(value['quantity']))
        if value['in_transit_planned_quantity'] is not None:
            value['in_transit_planned_quantity'] = quantity_string(int(value['in_transit_planned_quantity']))
        value['valuation'] = '未估值'
        quantities.append(value)
    return dict(items=quantities,total=result['total'],page=page,limit=limit,snapshot_at=result['snapshot_at'],
                totals=[dict(sku_id=sku_id,quantity=quantity,valuation='未估值') for sku_id,quantity in totals.items()],
                as_of=as_of,basis=basis if as_of is not None else None)

"""Transfer-specific physical observations and linked ordinary adjustments."""
from datetime import date, datetime
from sqlalchemy import select, text
from backend.application import warehouse
from backend.infrastructure import stock_store, store
from backend.infrastructure.models import StockDifference, StockDifferenceAdjustment, StockTransfer, StockTransferLine, StockTransferFundReference, new_id
from backend.kernel.accounting import DomainError
from backend.kernel.stock import quantity_to_minor, quantity_string


def get_difference(db, identifier):
    item = db.get(StockDifference,identifier)
    if item is None: raise DomainError('差异不存在',404)
    return item


def difference_view(db, item):
    sku = stock_store.get_sku(db,item.sku_id)
    adjustments = stock_store.adjustments(db,item.id)
    active = next((a for a in adjustments if a.status in ('pending','in_transit','completed')),None)
    return {key:getattr(item,key) for key in ('id','stock_transfer_id','confirmation_id','transfer_line_id','location_id','sku_id','comparison_at','basis','actor_id','payload','created_at')} | dict(location_name=store.get_location(db,item.location_id).name,sku_name=sku.name,unit=sku.unit,expected_quantity=quantity_string(item.expected_minor),observed_quantity=quantity_string(item.observed_minor),delta=quantity_string(item.delta_minor),status='resolved' if active and active.status == 'completed' else 'adjusting' if active else 'unresolved',adjustments=[dict(id=a.id,status=a.status,action_kind=a.action_kind) for a in adjustments])


def register_difference(db,user,identifier,data):
    warehouse.authorize(db,user,trusted=True)
    request = dict(stock_transfer_id=identifier,**data)
    previous = db.scalar(select(StockDifference).where(StockDifference.actor_id == user.id,StockDifference.idempotency_key == data['idempotency_key']))
    if previous:
        if previous.payload != request: raise DomainError('幂等键已用于不同内容',409)
        return difference_view(db,previous)
    transfer = warehouse.get_transfer(db,identifier)
    store.refresh(db,transfer)
    if transfer.status != 'completed': raise DomainError('原转移尚未完成',409)
    line = next((line for line in stock_store.lines(db,identifier) if line.id == data['line_id']),None)
    location_id = data['location_id']
    if line is None or location_id not in (transfer.source_location_id,transfer.destination_location_id) or stock_store.get_profile(db,location_id).kind != 'physical': raise DomainError('须选择原转移明细及实际端点')
    if not data['basis'].strip(): raise DomainError('须填写依据')
    observed = quantity_to_minor(data['observed_quantity'],allow_zero=True)
    delta = observed-line.quantity_minor if location_id == transfer.destination_location_id else line.quantity_minor-observed
    if delta == 0: raise DomainError('差额不能为零')
    confirmation = next(c for c in stock_store.confirmations(db,identifier) if c.status == 'completed')
    if any(d.transfer_line_id == line.id and d.location_id == location_id for d in stock_store.differences(db,transfer_id=identifier)): raise DomainError('该完成明细位置已登记差异',409)
    item = stock_store.create(db,StockDifference,dict(stock_transfer_id=identifier,confirmation_id=confirmation.id,transfer_line_id=line.id,location_id=location_id,sku_id=line.sku_id,expected_minor=line.quantity_minor,observed_minor=observed,delta_minor=delta,comparison_at=datetime.fromisoformat(data['comparison_at']),basis=data['basis'],actor_id=user.id,payload=request,idempotency_key=data['idempotency_key']))
    warehouse.audit(db,transfer,user,'difference_registered',dict(difference_id=item.id,delta=quantity_string(delta)),request)
    return difference_view(db,item)


def create_adjustment(db,user,identifier,data):
    warehouse.authorize(db,user,trusted=True)
    request = dict(difference_id=identifier,**data)
    previous = stock_store.existing_action(db,user.id,'difference_adjustment',data['idempotency_key'])
    if previous:
        if previous.request_payload != request: raise DomainError('幂等键已用于不同内容',409)
        return warehouse.transfer_view(db,warehouse.get_transfer(db,previous.stock_transfer_id))
    difference = get_difference(db,identifier)
    boundary = stock_store.get_profile(db,data['external_location_id'])
    if boundary is None: raise DomainError('外部调整位置不存在',404)
    if not data['basis'].strip(): raise DomainError('须填写依据')
    if any(a.status in ('pending','in_transit','completed') for a in stock_store.adjustments(db,identifier)): raise DomainError('差异已有有效调整',409)
    action = 'adjustment_gain' if difference.delta_minor > 0 else 'adjustment_loss'
    source,target = (data['external_location_id'],difference.location_id) if difference.delta_minor > 0 else (difference.location_id,data['external_location_id'])
    # Child identity is server-owned; action replay above keeps the client key.
    transfer_id = new_id()
    child_key = 'difference-adjustment:' + transfer_id
    while stock_store.existing_submission(db,user.id,child_key) is not None:
        transfer_id = new_id()
        child_key = 'difference-adjustment:' + transfer_id
    payload = dict(source_location_id=source,destination_location_id=target,action_kind=action,effective_date=data['effective_date'],description='转移核对差异调整',basis=data['basis'],source_reference='stock-difference:'+identifier,fund_transfer_ids=[],lines=[dict(sku_id=difference.sku_id,quantity=quantity_string(abs(difference.delta_minor)))],idempotency_key=child_key)
    item = stock_store.create(db,StockTransfer,dict(id=transfer_id,source_location_id=source,destination_location_id=target,action_kind=action,effective_date=date.fromisoformat(data['effective_date']),description=payload['description'],basis=data['basis'],source_reference=payload['source_reference'],actor_id=user.id,status='pending',payload=payload,idempotency_key=payload['idempotency_key']))
    stock_store.create(db,StockDifferenceAdjustment,dict(stock_transfer_id=item.id,difference_id=identifier))
    lines = warehouse.validate(db,payload,item.id)
    for line in lines: stock_store.create(db,StockTransferLine,line | dict(transfer_id=item.id))
    warehouse.approve(db,item,user,'automatic')
    warehouse.audit(db,item,user,'difference_adjustment',item.approval_snapshot,request)
    return warehouse.transfer_view(db,item)


def add_fund_reference(db,user,identifier,data):
    warehouse.authorize(db,user,trusted=True)
    request = dict(transfer_id=identifier,**data)
    previous = stock_store.existing_action(db,user.id,'fund_reference_added',data['idempotency_key'])
    if previous:
        if previous.request_payload != request: raise DomainError('幂等键已用于不同内容',409)
        return warehouse.transfer_view(db,warehouse.get_transfer(db,identifier))
    transfer = warehouse.get_transfer(db,identifier)
    if store.get_transfer(db,data['fund_transfer_id']) is None: raise DomainError('资金引用不存在',404)
    if db.get(StockTransferFundReference,(identifier,data['fund_transfer_id'])) is None:
        stock_store.create(db,StockTransferFundReference,dict(stock_transfer_id=identifier,fund_transfer_id=data['fund_transfer_id']))
    warehouse.audit(db,transfer,user,'fund_reference_added',dict(fund_transfer_id=data['fund_transfer_id']),request)
    return warehouse.transfer_view(db,transfer)


def list_differences(db,filters=None):
    with store.read_snapshot(db) as snapshot:
        timestamp = snapshot.scalar(text('SELECT transaction_timestamp()'))
        return [difference_view(snapshot,item) | dict(snapshot_at=timestamp) for item in stock_store.differences(snapshot,**(filters or {}))]

def difference_detail(db,identifier):
    with store.read_snapshot(db) as snapshot:
        timestamp = snapshot.scalar(text('SELECT transaction_timestamp()'))
        return difference_view(snapshot,get_difference(snapshot,identifier)) | dict(snapshot_at=timestamp)

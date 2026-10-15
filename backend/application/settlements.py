"""Private-account settlements are an application service over ordinary transfers."""
from backend.infrastructure import store, settlement_store
from backend.infrastructure.models import SettlementMatch
from backend.application import funds
from backend.application.agent_access import require_operator
from backend.application.members import authorize_write
from backend.kernel.accounting import DomainError, yuan_to_minor

def settlement_account(db,transfer):
    source=store.get_account(db,transfer.source_account_id)
    destination=store.get_account(db,transfer.destination_account_id)
    if source.kind=='public' and destination.kind=='private': return destination.id,'expense'
    if source.kind=='private' and destination.kind=='public': return source.id,'receipt'
    raise DomainError('结算须在公账与私账之间进行')

def item_account(db,transfer):
    source=store.get_account(db,transfer.source_account_id)
    destination=store.get_account(db,transfer.destination_account_id)
    if source.kind=='private' and destination.kind=='external': return source.id,'expense'
    if source.kind=='external' and destination.kind=='private': return destination.id,'receipt'
    return None

def validate_matches(db,settlement,allocations):
    if settlement.status!='posted' or settlement.reversal_of: raise DomainError('结算付款须为已过账的普通转移',409)
    account_id,direction=settlement_account(db,settlement)
    if not allocations: raise DomainError('请选择待结算记录')
    seen=set(); result=[]
    for allocation in allocations:
        item_id=allocation['item_transfer_id']; amount=yuan_to_minor(allocation['amount'])
        item=funds.get_transfer(db,item_id)
        if item.status!='posted' or item.reversal_of: raise DomainError('原收支须已批准过账',409)
        if item_account(db,item)!=(account_id,direction): raise DomainError('匹配须对应同一私账及相应收支方向')
        if item_id in seen or db.get(SettlementMatch,(settlement.id,item_id)): raise DomainError('不能重复匹配同一记录')
        seen.add(item_id)
        remaining=item.amount_minor-settlement_store.matched(db,item_id,'item_transfer_id')
        if amount>remaining: raise DomainError('匹配金额超过原收支未结金额')
        result.append((item_id,amount))
    remaining=settlement.amount_minor-settlement_store.matched(db,settlement.id,'settlement_transfer_id')
    if sum(amount for _,amount in result)>remaining: raise DomainError('匹配总额超过付款未匹配金额')
    return result

def record_matches(db,user,settlement,allocations, *, access=None):
    require_operator(user, access)
    values=validate_matches(db,settlement,allocations)
    settlement_store.add(db,settlement.id,values)
    store.audit(db,settlement.id,user.id,'settlement_matched','；'.join(f'{i}：{a} 分' for i,a in values), access=access)
    return dict(transfer=funds.transfer_view(db,settlement,True),matches=[dict(item_transfer_id=i,amount_minor=a,effective=True) for i,a in values])

def create(db,user,data, *, access=None):
    authorize_write(db,user)
    require_operator(user, access)
    settlement=funds.submit(db,user,data['transfer'], access=access, submit_mode='direct' if access else None)
    return record_matches(db,user,settlement,data['allocations'], access=access)

def add_matches(db,user,transfer_id,allocations, *, access=None):
    authorize_write(db,user)
    require_operator(user, access)
    return record_matches(db,user,funds.get_transfer(db,transfer_id),allocations, access=access)

def overview(db,account_id):
    from backend.application.catalogs import catalog_account_view
    with store.read_snapshot(db) as snapshot:
        account=store.get_account(snapshot,account_id)
        if not account: raise DomainError('账户不存在',404)
        if account.kind!='private': raise DomainError('请选择私账账户')
        expenses=[];receipts=[];settlements=[]
        all_matches=settlement_store.matches(snapshot)
        for transfer in store.transfers(snapshot):
            if account_id not in (transfer.source_account_id,transfer.destination_account_id): continue
            kind=item_account(snapshot,transfer)
            if kind and not transfer.reversal_of:
                settled=settlement_store.matched(snapshot,transfer.id,'item_transfer_id')
                row=dict(transfer=funds.transfer_view(snapshot,transfer),settled_minor=settled,
                         outstanding_minor=transfer.amount_minor-settled if transfer.status=='posted' else 0)
                (expenses if kind[1]=='expense' else receipts).append(row)
            else:
                try: settlement_account(snapshot,transfer)
                except DomainError: continue
                if transfer.reversal_of: continue
                linked=[m for m in all_matches if m.settlement_transfer_id==transfer.id]
                matched=settlement_store.matched(snapshot,transfer.id,'settlement_transfer_id')
                settlements.append(dict(transfer=funds.transfer_view(snapshot,transfer),matched_minor=matched,
                    unmatched_minor=transfer.amount_minor-matched if transfer.status=='posted' else 0,
                    matches=[dict(item_transfer_id=m.item_transfer_id,amount_minor=m.amount_minor,effective=settlement_store.effective(snapshot,m)) for m in linked]))
        return dict(account=catalog_account_view(snapshot,account),expenses=expenses,receipts=receipts,settlements=settlements)

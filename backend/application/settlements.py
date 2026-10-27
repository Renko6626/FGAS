"""Private-account settlements are an application service over ordinary transfers."""
from backend.infrastructure import store, settlement_store
from backend.application import funds
from backend.application.directory_views import by_code
from backend.infrastructure.models import FundAccount, Transfer
from backend.application.agent_access import require_operator
from backend.application.identity import authorize_write
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

def effective(match, endpoints):
    return all(endpoints[identifier].status == 'posted'
               for identifier in (match.settlement_transfer_id, match.item_transfer_id))


def matched_amounts(matches, endpoints):
    by_item = {}; by_settlement = {}
    for match in matches:
        if effective(match, endpoints):
            by_item[match.item_transfer_id] = by_item.get(match.item_transfer_id, 0) + match.amount_minor
            by_settlement[match.settlement_transfer_id] = by_settlement.get(match.settlement_transfer_id, 0) + match.amount_minor
    return by_item, by_settlement


def validate_matches(db,settlement,allocations):
    if settlement.status!='posted' or settlement.reversal_of: raise DomainError('结算付款须为已过账的普通转移',409)
    account_id,direction=settlement_account(db,settlement)
    if not allocations: raise DomainError('请选择待结算记录')
    matches, endpoints = settlement_store.matches_with_endpoints(
        db, {settlement.id, *(allocation['item_transfer_id'] for allocation in allocations)})
    by_item, by_settlement = matched_amounts(matches, endpoints)
    existing = {(match.settlement_transfer_id, match.item_transfer_id) for match in matches}
    seen=set(); result=[]
    for allocation in allocations:
        item_id=allocation['item_transfer_id']; amount=yuan_to_minor(allocation['amount'])
        item=endpoints.get(item_id)
        if item is None: raise DomainError('流水不存在', 404)
        if item.status!='posted' or item.reversal_of: raise DomainError('原收支须已批准过账',409)
        if item_account(db,item)!=(account_id,direction): raise DomainError('匹配须对应同一私账及相应收支方向')
        if item_id in seen or (settlement.id,item_id) in existing: raise DomainError('不能重复匹配同一记录')
        seen.add(item_id)
        remaining=item.amount_minor-by_item.get(item_id, 0)
        if amount>remaining: raise DomainError('匹配金额超过原收支未结金额')
        result.append((item_id,amount))
    remaining=settlement.amount_minor-by_settlement.get(settlement.id, 0)
    if sum(amount for _,amount in result)>remaining: raise DomainError('匹配总额超过付款未匹配金额')
    return result

def record_matches(db,user,settlement,allocations, *, access=None):
    require_operator(user, access)
    allocations = [dict(item_transfer_id=by_code(db,Transfer,row['item_transfer_code']).id,amount=row['amount']) for row in allocations]
    values=validate_matches(db,settlement,allocations)
    settlement_store.add(db,settlement.id,values)
    store.audit(db,settlement.id,user.id,'settlement_matched','；'.join(f'{store.get_transfer(db,i).code}：{a} 分' for i,a in values), access=access)
    return dict(transfer=funds.transfer_view(db,settlement,True),matches=[dict(item_transfer_code=store.get_transfer(db,i).code,amount_minor=a,effective=True) for i,a in values])

def create(db,user,data, *, access=None):
    authorize_write(db,user)
    require_operator(user, access)
    settlement=funds.submit(db,user,data['transfer'], access=access, submit_mode='direct' if access else None)
    return record_matches(db,user,settlement,data['allocations'], access=access)

def add_matches(db,user,transfer_id,allocations, *, access=None):
    authorize_write(db,user)
    require_operator(user, access)
    return record_matches(db,user,funds.get_transfer(db,transfer_id),allocations, access=access)


def outstanding(db, account_code=None, direction=None, kind=None, page=1, limit=20):
    with store.read_snapshot(db) as snapshot:
        account_id = by_code(snapshot,FundAccount,account_code).id if account_code is not None else None
        if account_id is not None:
            account = store.get_account(snapshot, account_id)
            if not account: raise DomainError('账户不存在', 404)
            if account.kind != 'private': raise DomainError('请选择私账账户')
        matches, endpoints = settlement_store.matches_with_endpoints(snapshot)
        by_item, by_settlement = matched_amounts(matches, endpoints)
        transfers = sorted(store.transfers(snapshot, status='posted'),
                           key=lambda item: (item.created_at, item.id), reverse=True)
        rows = []
        for transfer in transfers:
            if transfer.reversal_of: continue
            classification = item_account(snapshot, transfer)
            if classification:
                row_kind, matched = 'item', by_item.get(transfer.id, 0)
            else:
                try: classification = settlement_account(snapshot, transfer)
                except DomainError: continue
                row_kind, matched = 'payment', by_settlement.get(transfer.id, 0)
            private_id, row_direction = classification
            if account_id is not None and private_id != account_id: continue
            if direction is not None and row_direction != direction: continue
            if kind is not None and row_kind != kind: continue
            remaining = transfer.amount_minor - matched
            if remaining <= 0: continue
            source = store.get_account(snapshot, transfer.source_account_id)
            destination = store.get_account(snapshot, transfer.destination_account_id)
            rows.append(dict(
                account_code=store.get_account(snapshot,private_id).code, account_name=store.get_account(snapshot, private_id).name,
                kind=row_kind, direction=row_direction, transfer_code=transfer.code,
                effective_date=transfer.effective_date, description=transfer.description,
                counterparty=transfer.counterparty,
                source_account_code=source.code, source_account_name=source.name,
                destination_account_code=destination.code, destination_account_name=destination.name,
                amount_minor=transfer.amount_minor, matched_minor=matched, remaining_minor=remaining,
            ))
        start = (page - 1) * limit
        return dict(items=rows[start:start + limit], total=len(rows), page=page, limit=limit,
                    snapshot_at=store.snapshot_timestamp(snapshot))


def overview(db,account_code):
    from backend.application.catalogs import catalog_account_view
    with store.read_snapshot(db) as snapshot:
        account=by_code(snapshot,FundAccount,account_code)
        account_id=account.id
        if not account: raise DomainError('账户不存在',404)
        if account.kind!='private': raise DomainError('请选择私账账户')
        expenses=[];receipts=[];settlements=[]
        all_matches, endpoints = settlement_store.matches_with_endpoints(snapshot)
        by_item, by_settlement = matched_amounts(all_matches, endpoints)
        matches_by_settlement = {}
        for match in all_matches:
            matches_by_settlement.setdefault(match.settlement_transfer_id, []).append(match)
        for transfer in store.transfers(snapshot):
            if account_id not in (transfer.source_account_id,transfer.destination_account_id): continue
            kind=item_account(snapshot,transfer)
            if kind and not transfer.reversal_of:
                settled=by_item.get(transfer.id, 0)
                row=dict(transfer=funds.transfer_view(snapshot,transfer),settled_minor=settled,
                         outstanding_minor=transfer.amount_minor-settled if transfer.status=='posted' else 0)
                (expenses if kind[1]=='expense' else receipts).append(row)
            else:
                try: settlement_account(snapshot,transfer)
                except DomainError: continue
                if transfer.reversal_of: continue
                linked=matches_by_settlement.get(transfer.id, [])
                matched=by_settlement.get(transfer.id, 0)
                settlements.append(dict(transfer=funds.transfer_view(snapshot,transfer),matched_minor=matched,
                    unmatched_minor=transfer.amount_minor-matched if transfer.status=='posted' else 0,
                    matches=[dict(item_transfer_code=endpoints[m.item_transfer_id].code,amount_minor=m.amount_minor,effective=effective(m,endpoints)) for m in linked]))
        return dict(account=catalog_account_view(snapshot,account),expenses=expenses,receipts=receipts,settlements=settlements)

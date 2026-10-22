from typing import Literal
from backend.application.agent_access import AgentAccess, auto_apply, require_operator, source_fields
from backend.infrastructure import store
from backend.infrastructure.models import now
from backend.kernel.accounting import DomainError, balanced_transfer
from backend.modules.funds.plans import transfer_plan


def require_trusted(user):
    if user.role not in ('admin', 'trusted'): raise DomainError('需要受信任用户权限', 403)
def get_transfer(db, identifier):
    item = store.get_transfer(db, identifier)
    if not item: raise DomainError('流水不存在', 404)
    return item

def validate(db, source, destination, amount):
    lines = transfer_plan(source, destination, amount)
    if any(store.get_account(db, line.account_id) is None for line in lines):
        raise DomainError('记账对象不存在', 404)
    return lines

def post(db, item, user, mode, *, access=None):
    require_operator(user, access)
    if not user.active or user.role not in ('admin', 'trusted'): raise DomainError('无过账权限', 403)
    if item.status != 'pending': raise DomainError('流水已处理', 409)
    if not all(store.get_account(db, aid) for aid in (item.source_account_id, item.destination_account_id)):
        raise DomainError('记账对象不存在', 404)
    if item.reversal_of:
        original = get_transfer(db, item.reversal_of)
        if original.status != 'posted': raise DomainError('原流水已冲销或不可冲销', 409)
        original.status = 'reversed'
        original.version += 1
    for line in balanced_transfer(item.source_account_id, item.destination_account_id, item.amount_minor):
        store.add_journal(db, item.id, line)
    item.status = 'posted'
    item.approved_by = user.id
    item.approval_mode = mode
    item.version += 1
    item.posted_at = now()
    store.audit(db, item.id, user.id, 'posted', mode, access=access)
    store.flush(db)

def submit(db, user, data, reversal_of=None, reason=None, *, access: AgentAccess | None = None, submit_mode: Literal['propose', 'direct'] | None = None):
    store.lock(db)
    store.refresh(db,user)
    if not user.active: raise DomainError('用户已停用',403)
    apply = auto_apply(user, access=access, submit_mode=submit_mode)
    lines=validate(db,data['source_account_id'],data['destination_account_id'],data['amount'])
    if not reversal_of and any(not store.get_account(db,aid).active for aid in (data['source_account_id'],data['destination_account_id'])):
        raise DomainError('账户已停用',409)
    if reversal_of:
        original=get_transfer(db,reversal_of)
        store.refresh(db,original)
        if original.status != 'posted' or store.existing_reversal(db,reversal_of): raise DomainError('流水已有冲销或不可冲销',409)
    from datetime import date
    values={k:data.get(k,[] if k=='tags' else '' if k=='description' else None) for k in ('source_account_id','destination_account_id','description','counterparty','tags')}
    values.update(effective_date=date.fromisoformat(data['effective_date']),amount_minor=lines[0].credit_minor,actor_id=user.id,status='pending',reversal_of=reversal_of,reason=reason)
    item=store.create_transfer(db,values | source_fields(access))
    store.audit(db,item.id,user.id,'submitted',reason or '', access=access)
    if apply: post(db,item,user,'agent_direct' if access else 'automatic', access=access)
    return item

def decide(db, user, identifier, version, rejection=None, *, access=None):
    store.lock(db)
    store.refresh(db, user)
    require_operator(user, access)
    require_trusted(user)
    if not user.active: raise DomainError('用户已停用', 403)
    item = get_transfer(db, identifier)
    store.refresh(db, item)
    if item.version != version or item.status != 'pending': raise DomainError('版本已变化或流水已处理', 409)
    if rejection is None: post(db, item, user, 'agent_approval' if access else 'manual', access=access)
    else:
        item.status = 'rejected'
        item.version += 1
        item.approved_by = user.id
        item.reason = rejection
        store.audit(db, item.id, user.id, 'rejected', rejection, access=access)
    return item

def balance(db, account, *, as_of=None, basis='posted'):
    return store.balance_delta(db, account.id, as_of=as_of, basis=basis)

def account_view(db, account):
    return {key:getattr(account,key) for key in ('id','name','kind','member_id','avatar_url','tags','active')} | dict(balance_minor=balance(db,account))

def transfer_view(db, item, detail=False):
    value = {key: getattr(item, key) for key in ('id', 'source_account_id', 'destination_account_id', 'amount_minor', 'effective_date', 'description', 'tags', 'counterparty', 'actor_id', 'approved_by', 'approval_mode', 'status', 'version', 'reversal_of', 'reason', 'created_at', 'posted_at', 'submitted_credential_id', 'submitted_credential_name')}
    for side in ('source', 'destination'):
        value[side + '_account_name'] = store.get_account(db, getattr(item, side + '_account_id')).name
    value['actor_name'] = store.get_user(db, item.actor_id).display_name
    value['approved_by_name'] = store.get_user(db, item.approved_by).display_name if item.approved_by else None
    if detail:
        value['journal_lines'] = store.journal(db, item.id)
        value['audit'] = store.audit_events(db, item.id)
    return value

def preview(db, user, data, *, access: AgentAccess | None = None, submit_mode: Literal['propose', 'direct'] | None = None):
    apply = auto_apply(user, access=access, submit_mode=submit_mode)
    lines = validate(db, data['source_account_id'], data['destination_account_id'], data['amount'])
    return {'amount_minor': lines[0].credit_minor, 'status': 'posted' if apply else 'pending', 'source_account_name': store.get_account(db, data['source_account_id']).name, 'destination_account_name': store.get_account(db, data['destination_account_id']).name, 'journal_lines': [vars(l) for l in lines]}

def list_transfers(db, status=None, tag=None, q=None, date_from=None, date_to=None, sort='created_at', page=1, limit=20):
    items, total = store.transfer_page(db, status=status, tag=tag, q=q, date_from=date_from, date_to=date_to,
                                       sort=sort, page=page, limit=limit)
    return dict(items=[transfer_view(db, item) for item in items], total=total, page=page, limit=limit)

def reverse(db, user, identifier, reason, *, access=None):
    require_operator(user, access)
    store.lock(db)
    original = get_transfer(db, identifier)
    store.refresh(db, original)
    payload = dict(source_account_id=original.destination_account_id, destination_account_id=original.source_account_id, amount=f'{original.amount_minor // 100}.{original.amount_minor % 100:02d}', effective_date=original.effective_date.isoformat(), description=f'冲销：{original.description}', counterparty=original.counterparty, tags=original.tags)
    return transfer_view(db, submit(db, user, payload, original.id, reason, access=access, submit_mode='direct' if access else None), True)

def summary(db, *, as_of=None, basis='posted'):
    values = store.fund_balances(db, as_of=as_of, basis=basis)
    return {'accounts': values, 'total_minor': sum(r['balance_minor'] for r in values), 'currency': 'CNY'}

from sqlalchemy import select, text, func
from backend.infrastructure.models import Account, FundAccount, Transfer, JournalLine, Audit, User
from backend.kernel.accounting import DomainError, balanced_transfer
from backend.modules.funds.plans import transfer_plan


def lock(db): db.execute(text('SELECT pg_advisory_xact_lock(734621)'))
def require_trusted(user):
    if user.role not in ('admin', 'trusted'): raise DomainError('需要受信任用户权限', 403)
def get_transfer(db, identifier):
    item = db.get(Transfer, identifier)
    if not item: raise DomainError('流水不存在', 404)
    return item

def validate(db, source, destination, amount):
    lines = transfer_plan(source, destination, amount)
    if any(db.get(Account, line.account_id) is None for line in lines):
        raise DomainError('记账对象不存在', 404)
    return lines

def post(db, item, user, mode):
    if not user.active or user.role not in ('admin', 'trusted'): raise DomainError('无过账权限', 403)
    if item.status != 'pending': raise DomainError('流水已处理', 409)
    if not all(db.get(Account, aid) for aid in (item.source_account_id, item.destination_account_id)):
        raise DomainError('记账对象不存在', 404)
    if item.reversal_of:
        original = get_transfer(db, item.reversal_of)
        if original.status != 'posted': raise DomainError('原流水已冲销或不可冲销', 409)
        original.status = 'reversed'
        original.version += 1
    for line in balanced_transfer(item.source_account_id, item.destination_account_id, item.amount_minor):
        db.add(JournalLine(transfer_id=item.id, account_id=line.account_id, debit_minor=line.debit_minor, credit_minor=line.credit_minor))
    item.status = 'posted'
    item.approved_by = user.id
    item.approval_mode = mode
    item.version += 1
    db.add(Audit(transfer_id=item.id, actor_id=user.id, action='posted', detail=mode))
    db.flush()

def submit(db, user, data, reversal_of=None, reason=None):
    lock(db)
    # Resolve persisted role inside the write transaction, rather than trusting request data.
    db.refresh(user)
    if not user.active: raise DomainError('用户已停用', 403)
    payload = dict(data, reversal_of=reversal_of, reason=reason)
    old = db.scalar(select(Transfer).where(Transfer.actor_id == user.id, Transfer.idempotency_key == data['idempotency_key']))
    if old:
        if old.payload != payload: raise DomainError('幂等标识已用于不同内容', 409)
        return old
    lines = validate(db, data['source_account_id'], data['destination_account_id'], data['amount'])
    if reversal_of:
        original = get_transfer(db, reversal_of)
        existing = db.scalar(select(Transfer).where(Transfer.reversal_of == reversal_of, Transfer.status.in_(['pending', 'posted'])))
        if original.status != 'posted' or existing: raise DomainError('流水已有冲销或不可冲销', 409)
    item = Transfer(**{k: data[k] for k in ('source_account_id', 'destination_account_id', 'effective_date', 'description', 'counterparty', 'idempotency_key')}, amount_minor=lines[0].credit_minor, actor_id=user.id, status='pending', payload=payload, reversal_of=reversal_of, reason=reason)
    # JSON payload dates use canonical strings; ORM date uses real date.
    from datetime import date
    item.effective_date = date.fromisoformat(item.effective_date)
    db.add(item)
    db.flush()
    db.add(Audit(transfer_id=item.id, actor_id=user.id, action='submitted', detail=reason or ''))
    if user.role in ('admin', 'trusted'): post(db, item, user, 'automatic')
    return item

def decide(db, user, identifier, version, rejection=None):
    lock(db)
    db.refresh(user)
    require_trusted(user)
    if not user.active: raise DomainError('用户已停用', 403)
    item = get_transfer(db, identifier)
    if item.version != version or item.status != 'pending': raise DomainError('版本已变化或流水已处理', 409)
    if rejection is None: post(db, item, user, 'manual')
    else:
        item.status = 'rejected'
        item.version += 1
        item.approved_by = user.id
        item.reason = rejection
        db.add(Audit(transfer_id=item.id, actor_id=user.id, action='rejected', detail=rejection))
    return item

def balance(db, account):
    value = db.scalar(select(func.coalesce(func.sum(JournalLine.debit_minor - JournalLine.credit_minor), 0)).where(JournalLine.account_id == account.id))
    return int(value) * (1 if account.kind in ('asset', 'expense') else -1)

def account_view(db, account):
    return dict(id=account.id, name=account.name, kind=account.kind, tags=account.tags, is_fund=db.get(FundAccount, account.id) is not None, balance_minor=balance(db, account))

def transfer_view(db, item, detail=False):
    value = {key: getattr(item, key) for key in ('id', 'source_account_id', 'destination_account_id', 'amount_minor', 'effective_date', 'description', 'counterparty', 'actor_id', 'approved_by', 'approval_mode', 'status', 'version', 'reversal_of', 'reason', 'created_at')}
    for side in ('source', 'destination'):
        value[side + '_account_name'] = db.get(Account, getattr(item, side + '_account_id')).name
    value['actor_name'] = db.get(User, item.actor_id).display_name
    value['approved_by_name'] = db.get(User, item.approved_by).display_name if item.approved_by else None
    if detail:
        value['journal_lines'] = [dict(account_id=l.account_id, debit_minor=l.debit_minor, credit_minor=l.credit_minor) for l in db.scalars(select(JournalLine).where(JournalLine.transfer_id == item.id))]
        value['audit'] = [dict(actor_id=a.actor_id, action=a.action, detail=a.detail, created_at=a.created_at) for a in db.scalars(select(Audit).where(Audit.transfer_id == item.id).order_by(Audit.created_at))]
    return value

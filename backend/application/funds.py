from backend.infrastructure import store
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

def post(db, item, user, mode):
    if not user.active or user.role not in ('admin', 'trusted'): raise DomainError('无过账权限', 403)
    if item.status != 'pending': raise DomainError('流水已处理', 409)
    if not all(store.get_account(db, aid) for aid in (item.source_account_id, item.destination_account_id)):
        raise DomainError('记账对象不存在', 404)
    validate_business_post(db, item, user)
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
    store.audit(db, item.id, user.id, 'posted', mode)
    store.flush(db)

def validate_business_post(db, item, user) -> None:
    from backend.modules.member_claims.rules import validate_confirmation
    original = get_transfer(db, item.reversal_of) if item.reversal_of else item
    claim = store.get_claim(db, original.id)
    repayment = store.get_repayment(db, original.id)
    if original.reversal_of:
        linked = original.reversal_of
        if store.get_claim(db, linked) or store.get_repayment(db, linked):
            raise DomainError('业务冲销记录不能再次冲销', 409)
    if claim or repayment:
        require_trusted(user)
        if claim:
            if item.reversal_of:
                if store.claim_repaid_minor(db, original.id): raise DomainError('垫付已有有效偿还，不能冲销', 409)
            else:
                member = store.get_member(db, claim.member_id)
                if not member or item.source_account_id != member.account_id:
                    raise DomainError('垫付来源须为该成员往来科目')
                if claim.confirmed_minor is None:
                    raise DomainError('请通过垫付确认入口 /api/member-claims/{id}/confirm 确认金额', 409)
                validate_confirmation(claim.declared_minor, claim.confirmed_minor, claim.confirmation_reason or '')
                if item.amount_minor != claim.confirmed_minor: raise DomainError('转移金额与确认金额不一致', 409)


def validate_business(db, business, data, amount_minor, defer_post):
    """Check marker identity and endpoints before persisting any marker."""
    kind = business.get('kind')
    if kind not in ('member_claim', 'repayment'): raise DomainError('业务标记类型无效')
    member = store.get_member(db, business.get('member_id'))
    if not member: raise DomainError('成员不存在', 404)
    account = store.get_account(db, member.account_id)
    if not account or account.kind != 'liability' or store.is_fund(db, member.account_id):
        raise DomainError('成员往来科目无效')
    if not isinstance(business.get('basis'), str) or not business['basis'].strip():
        raise DomainError('须填写依据')
    if kind == 'member_claim':
        if data['source_account_id'] != member.account_id: raise DomainError('垫付来源须为该成员往来科目')
        declared = business.get('declared_minor')
        confirmed = business.get('confirmed_minor')
        if type(declared) is not int or declared <= 0: raise DomainError('申报金额无效')
        if confirmed is not None and (type(confirmed) is not int or not 0 < confirmed <= declared):
            raise DomainError('确认金额无效')
        if amount_minor != (declared if confirmed is None else confirmed): raise DomainError('转移金额与垫付标记不一致')
        if confirmed is None and not defer_post: raise DomainError('未确认垫付不能过账')
        if confirmed is not None and confirmed != declared and not (business.get('confirmation_reason') or '').strip():
            raise DomainError('确认金额不一致须填写原因')
    else:
        if data['destination_account_id'] != member.account_id or not store.is_fund(db, data['source_account_id']):
            raise DomainError('偿还须从组织资金付至该成员往来科目')
        if business.get('allocation_mode') not in ('oldest_first', 'manual'): raise DomainError('匹配方式无效')
        allocations = business.get('allocations', [])
        if not isinstance(allocations, list) or not allocations: raise DomainError('偿还须提供匹配')
        seen = set()
        total = 0
        for allocation in allocations:
            claim_id = allocation.get('claim_id')
            claim = store.get_claim(db, claim_id)
            amount = allocation.get('amount_minor')
            if not claim or claim.member_id != member.id: raise DomainError('匹配垫付须属于该成员')
            if claim_id in seen or type(amount) is not int or amount <= 0: raise DomainError('匹配金额或重复匹配无效')
            seen.add(claim_id)
            total += amount
        if total != amount_minor: raise DomainError('匹配总额须等于偿还金额')


def save_business(db, item, business):
    values = dict(transfer_id=item.id, member_id=business['member_id'], basis=business['basis'])
    if business['kind'] == 'member_claim':
        from backend.infrastructure.models import now
        confirmed = business.get('confirmed_minor')
        values.update(declared_minor=business['declared_minor'], confirmed_minor=confirmed,
                      confirmation_reason=business.get('confirmation_reason'),
                      confirmed_at=now() if confirmed is not None else None)
        store.create_claim(db, values)
    else:
        values['allocation_mode'] = business['allocation_mode']
        allocations = [{key: allocation[key] for key in ('claim_id', 'amount_minor')} for allocation in business['allocations']]
        store.create_repayment(db, values, allocations)


def submit(db, user, data, reversal_of=None, reason=None, *, business: dict | None=None, defer_post: bool=False):
    store.lock(db)
    # Resolve persisted role inside the write transaction, rather than trusting request data.
    store.refresh(db, user)
    if not user.active: raise DomainError('用户已停用', 403)
    if business is not None or defer_post: require_trusted(user)
    # Internal controls are part of the original request, server timestamps are not.
    from copy import deepcopy
    payload = deepcopy(dict(data, reversal_of=reversal_of, reason=reason))
    if business is not None:
        payload['business'] = deepcopy({key: value for key, value in business.items() if key != 'confirmed_at'})
        payload['defer_post'] = defer_post
    elif defer_post:
        payload['defer_post'] = True
    old = store.existing_submission(db, user.id, data['idempotency_key'])
    if old:
        if old.payload != payload: raise DomainError('幂等标识已用于不同内容', 409)
        return old
    lines = validate(db, data['source_account_id'], data['destination_account_id'], data['amount'])
    if business is not None:
        if reversal_of: raise DomainError('冲销不能新建业务标记')
        validate_business(db, business, data, lines[0].credit_minor, defer_post)
    if reversal_of:
        original = get_transfer(db, reversal_of)
        store.refresh(db, original)
        if store.get_claim(db, original.id) or store.get_repayment(db, original.id) or (original.reversal_of and (store.get_claim(db, original.reversal_of) or store.get_repayment(db, original.reversal_of))):
            require_trusted(user)
        existing = store.existing_reversal(db, reversal_of)
        if original.status != 'posted' or existing: raise DomainError('流水已有冲销或不可冲销', 409)
    from datetime import date
    values = {k: data[k] for k in ('source_account_id', 'destination_account_id', 'description', 'counterparty', 'idempotency_key')}
    values.update(effective_date=date.fromisoformat(data['effective_date']), amount_minor=lines[0].credit_minor, actor_id=user.id, status='pending', payload=payload, reversal_of=reversal_of, reason=reason)
    item = store.create_transfer(db, values)
    if business is not None: save_business(db, item, business)
    store.audit(db, item.id, user.id, 'submitted', reason or '')
    if user.role in ('admin', 'trusted') and not defer_post: post(db, item, user, 'automatic')
    return item

def decide(db, user, identifier, version, rejection=None):
    store.lock(db)
    store.refresh(db, user)
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
        store.audit(db, item.id, user.id, 'rejected', rejection)
    return item

def balance(db, account):
    return store.balance_delta(db, account.id) * (1 if account.kind in ('asset', 'expense') else -1)

def account_view(db, account):
    return dict(id=account.id, name=account.name, kind=account.kind, tags=account.tags, is_fund=store.is_fund(db, account.id), balance_minor=balance(db, account))

def transfer_view(db, item, detail=False):
    value = {key: getattr(item, key) for key in ('id', 'source_account_id', 'destination_account_id', 'amount_minor', 'effective_date', 'description', 'counterparty', 'actor_id', 'approved_by', 'approval_mode', 'status', 'version', 'reversal_of', 'reason', 'created_at')}
    for side in ('source', 'destination'):
        value[side + '_account_name'] = store.get_account(db, getattr(item, side + '_account_id')).name
    value['actor_name'] = store.get_user(db, item.actor_id).display_name
    value['approved_by_name'] = store.get_user(db, item.approved_by).display_name if item.approved_by else None
    business_id = item.reversal_of or item.id
    claim = store.get_claim(db, business_id)
    repayment = store.get_repayment(db, business_id)
    marker = claim or repayment
    value['business'] = dict(kind='member_claim' if claim else 'repayment', id=business_id, member_id=marker.member_id) if marker else None
    if detail:
        value['journal_lines'] = store.journal(db, item.id)
        value['audit'] = store.audit_events(db, item.id)
    return value

def preview(db, user, data):
    lines = validate(db, data['source_account_id'], data['destination_account_id'], data['amount'])
    return {'amount_minor': lines[0].credit_minor, 'status': 'pending' if user.role == 'untrusted' else 'posted', 'source_account_name': store.get_account(db, data['source_account_id']).name, 'destination_account_name': store.get_account(db, data['destination_account_id']).name, 'journal_lines': [vars(l) for l in lines]}

def list_transfers(db, status=None):
    return [transfer_view(db, item) for item in store.transfers(db, status)]

def reverse(db, user, identifier, reason, key):
    store.lock(db)
    original = get_transfer(db, identifier)
    # Confirmation can change a pending claim's amount before this lock is acquired.
    store.refresh(db, original)
    payload = dict(source_account_id=original.destination_account_id, destination_account_id=original.source_account_id, amount=f'{original.amount_minor // 100}.{original.amount_minor % 100:02d}', effective_date=original.effective_date.isoformat(), description=f'冲销：{original.description}', counterparty=original.counterparty, idempotency_key=key)
    return transfer_view(db, submit(db, user, payload, original.id, reason), True)

def summary(db):
    values = store.fund_balances(db)
    return {'accounts': values, 'total_minor': sum(r['balance_minor'] for r in values), 'currency': 'CNY'}

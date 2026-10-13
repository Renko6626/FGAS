"""Member directory and its associated non-fund liability accounts."""
from backend.infrastructure import store
from backend.application.funds import require_trusted
from backend.kernel.accounting import DomainError


def member_view(item):
    return dict(id=item.id, name=item.name, note=item.note, account_id=item.account_id)


def list_members(db):
    return [member_view(item) for item in store.members(db)]


def authorize_write(db, user):
    store.lock(db)
    store.refresh(db, user)
    require_trusted(user)
    if not user.active: raise DomainError('用户已停用', 403)


def create_member(db, user, data: dict) -> dict:
    authorize_write(db, user)
    account = store.create_account(db, dict(name=data['name'], kind='liability', tags=[]), False)
    item = store.create_member(db, dict(name=data['name'], note=data.get('note', ''), account_id=account.id))
    return member_view(item)


def update_member(db, user, identifier: str, data: dict) -> dict:
    authorize_write(db, user)
    item = store.get_member(db, identifier)
    if not item: raise DomainError('成员不存在', 404)
    values = {key: data[key] for key in ('name', 'note') if key in data}
    store.update(item, values)
    if 'name' in values: store.get_account(db, item.account_id).name = values['name']
    store.flush(db)
    return member_view(item)


def claim_view(db, claim):
    from backend.application import funds
    item = funds.get_transfer(db, claim.transfer_id)
    repaid = store.claim_repaid_minor(db, item.id)
    confirmed = claim.confirmed_minor or 0
    return dict(id=item.id, member_id=claim.member_id, declared_minor=claim.declared_minor,
                confirmed_minor=claim.confirmed_minor, basis=claim.basis,
                confirmation_reason=claim.confirmation_reason, confirmed_at=claim.confirmed_at,
                repaid_minor=repaid, outstanding_minor=confirmed - repaid if item.status == 'posted' else 0,
                status=item.status, version=item.version, transfer=funds.transfer_view(db, item, True))


def get_claim(db, identifier: str) -> dict:
    claim = store.get_claim(db, identifier)
    if not claim: raise DomainError('垫付不存在', 404)
    return claim_view(db, claim)


def list_claims(db, member_id=None, status=None) -> list[dict]:
    return [claim_view(db, claim) for claim in store.claims(db, member_id, status)]


def submit_claim(db, user, data: dict) -> dict:
    from backend.application import funds
    from backend.kernel.accounting import yuan_to_minor
    from backend.modules.member_claims.rules import validate_confirmation
    authorize_write(db, user)
    member = store.get_member(db, data['member_id'])
    if not member: raise DomainError('成员不存在', 404)
    declared = yuan_to_minor(data['amount'])
    confirm_now = data['confirm_now']
    reason = data.get('confirmation_reason') or ''
    if not confirm_now and (data.get('confirmed_amount') is not None or reason):
        raise DomainError('待确认申报不能携带确认内容')
    confirmation_input = data['amount'] if data.get('confirmed_amount') is None else data['confirmed_amount']
    confirmed = yuan_to_minor(confirmation_input) if confirm_now else None
    if confirmed is not None: validate_confirmation(declared, confirmed, reason)
    business = dict(kind='member_claim', member_id=member.id, declared_minor=declared,
                    confirmed_minor=confirmed, basis=data['basis'], confirmation_reason=reason)
    values = dict(source_account_id=member.account_id, destination_account_id=data['destination_account_id'],
                  amount=data['amount'] if confirmed is None else f'{confirmed // 100}.{confirmed % 100:02d}',
                  effective_date=data['effective_date'], description=data.get('description', ''),
                  counterparty=None)
    item = funds.submit(db, user, values, business=business, defer_post=not confirm_now)
    return get_claim(db, item.id)


def confirm_claim(db, user, identifier: str, expected_version: int, confirmed_amount: str, reason: str='') -> dict:
    from backend.application import funds
    from backend.infrastructure.models import now
    from backend.kernel.accounting import yuan_to_minor
    from backend.modules.member_claims.rules import validate_confirmation
    authorize_write(db, user)
    claim = store.get_claim(db, identifier)
    if not claim: raise DomainError('垫付不存在', 404)
    item = funds.get_transfer(db, identifier)
    store.refresh(db, item)
    store.refresh(db, claim)
    if item.status != 'pending' or item.version != expected_version:
        raise DomainError('版本已变化或垫付已处理', 409)
    amount = yuan_to_minor(confirmed_amount)
    validate_confirmation(claim.declared_minor, amount, reason)
    claim.confirmed_minor = amount
    claim.confirmation_reason = reason
    claim.confirmed_at = now()
    item.amount_minor = amount
    store.audit(db, item.id, user.id, 'claim_confirmed', f'确认金额（分）：{amount}；原因：{reason}')
    funds.post(db, item, user, 'manual')
    return get_claim(db, identifier)


def reject_claim(db, user, identifier: str, expected_version: int, reason: str) -> dict:
    from backend.application import funds
    if not store.get_claim(db, identifier): raise DomainError('垫付不存在', 404)
    if not reason.strip(): raise DomainError('须填写拒绝原因')
    funds.decide(db, user, identifier, expected_version, reason)
    return get_claim(db, identifier)


def repayment_values(db, data):
    member = store.get_member(db, data['member_id'])
    if not member: raise DomainError('成员不存在', 404)
    return dict(source_account_id=data['source_account_id'], destination_account_id=member.account_id,
                amount=data['amount'], effective_date=data['effective_date'],
                description=data.get('description', ''), counterparty=None)


def preview_repayment(db, user, data: dict) -> dict:
    from backend.application import funds
    from backend.kernel.accounting import yuan_to_minor
    from backend.modules.member_claims.rules import allocate_oldest, validate_allocations
    require_trusted(user)
    values = repayment_values(db, data)
    amount = yuan_to_minor(data['amount'])
    if not store.is_fund(db, values['source_account_id']): raise DomainError('偿还来源须为组织资金账户')
    if not data['basis'].strip(): raise DomainError('须填写依据')
    claims = store.open_claims(db, data['member_id'])
    mode = data['allocation_mode']
    if mode == 'oldest_first':
        allocations = allocate_oldest(claims, amount)
    elif mode == 'manual':
        allocations = [(a['claim_id'], yuan_to_minor(a['amount'])) for a in data.get('allocations') or []]
    else: raise DomainError('匹配方式无效')
    validate_allocations(claims, data['member_id'], amount, allocations)
    versions = {claim.id: claim.version for claim in claims}
    lines = funds.validate(db, values['source_account_id'], values['destination_account_id'], values['amount'])
    return dict(amount_minor=amount, source_account_id=values['source_account_id'],
                destination_account_id=values['destination_account_id'], allocation_mode=mode,
                allocations=[dict(claim_id=identifier, amount=f'{value // 100}.{value % 100:02d}',
                                  expected_version=versions[identifier]) for identifier, value in allocations],
                journal_lines=[vars(line) for line in lines])


def submit_repayment(db, user, data: dict) -> dict:
    from backend.application import funds
    from backend.kernel.accounting import yuan_to_minor
    values = repayment_values(db, data)
    business = dict(kind='repayment', member_id=data['member_id'], basis=data['basis'],
                    allocation_mode=data['allocation_mode'], allocations=[dict(
                        claim_id=a['claim_id'], amount_minor=yuan_to_minor(a['amount']),
                        expected_version=a['expected_version']) for a in data['allocations']])
    item = funds.submit(db, user, values, business=business)
    return get_repayment(db, item.id)


def get_repayment(db, identifier: str) -> dict:
    from backend.application import funds
    repayment = store.get_repayment(db, identifier)
    if not repayment: raise DomainError('偿还不存在', 404)
    item = funds.get_transfer(db, identifier)
    reversal = store.existing_reversal(db, identifier)
    return dict(id=identifier, member_id=repayment.member_id, basis=repayment.basis,
                allocation_mode=repayment.allocation_mode, status=item.status, version=item.version,
                amount_minor=item.amount_minor, effective=item.status == 'posted',
                allocations=[dict(claim_id=a.claim_id, amount_minor=a.amount_minor)
                             for a in store.repayment_allocations(db, identifier)],
                reversal_id=reversal.id if reversal else None, transfer=funds.transfer_view(db, item, True))


def list_repayments(db, member_id: str | None=None) -> list[dict]:
    return [get_repayment(db, item.transfer_id) for item in store.repayments(db, member_id)]


def member_detail(db, identifier: str) -> dict:
    from backend.application import funds
    with store.read_snapshot(db) as snapshot:
        item = store.get_member(snapshot, identifier)
        if not item: raise DomainError('成员不存在', 404)
        return dict(member=member_view(item), **store.member_overview(snapshot, item),
                    claims=list_claims(snapshot, identifier), repayments=list_repayments(snapshot, identifier),
                    other_transfers=[funds.transfer_view(snapshot, transfer, True)
                                     for transfer in store.member_other_transfers(snapshot, item)])

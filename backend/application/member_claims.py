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

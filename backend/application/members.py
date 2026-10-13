from backend.infrastructure import store
from backend.application.funds import require_trusted
from backend.kernel.accounting import DomainError

def member_view(item): return dict(id=item.id,name=item.name,note=item.note)
def list_members(db): return [member_view(item) for item in store.members(db)]
def authorize_write(db,user):
    store.lock(db); store.refresh(db,user)
    if not user.active: raise DomainError('用户已停用',403)
    require_trusted(user)
def create_member(db,user,data):
    authorize_write(db,user)
    if not data['name'].strip(): raise DomainError('姓名不能为空')
    return member_view(store.create_member(db,data))
def update_member(db,user,identifier,data):
    authorize_write(db,user)
    item=store.get_member(db,identifier)
    if not item: raise DomainError('成员不存在',404)
    if 'name' in data and not data['name'].strip(): raise DomainError('姓名不能为空')
    store.update(item,data); store.flush(db); return member_view(item)

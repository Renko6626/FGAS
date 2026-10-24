from backend.infrastructure import store
from backend.application.identity import authorize_write
from backend.application.directory_views import member_view
from backend.kernel.accounting import DomainError

def list_members(db): return [member_view(item) for item in store.members(db)]
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

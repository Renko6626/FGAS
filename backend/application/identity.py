from backend.infrastructure import store
from backend.kernel.accounting import DomainError

def user_view(user): return dict(id=user.id, display_name=user.display_name, role=user.role, active=user.active)
def resolve(db, token):
    user = store.session_user(db, token)
    if not user or not user.active: raise DomainError('请先登录', 401)
    return user

def require_admin(user):
    if user.role != 'admin': raise DomainError('需要管理员权限', 403)
def login_users(db): return [user_view(u) for u in store.users(db, active_only=True)]
def login(db, identifier):
    user = store.get_user(db, identifier)
    if not user or not user.active: raise DomainError('用户不存在或已停用', 403)
    return user_view(user), store.create_session(db, user.id)

def logout(db, token): store.delete_session(db, token)
def users(db, actor):
    require_admin(actor)
    return [user_view(u) for u in store.users(db)]

def update_user(db, actor, identifier, values):
    store.lock(db)
    store.refresh(db, actor)
    require_admin(actor)
    if not actor.active: raise DomainError('用户已停用', 403)
    item = store.get_user(db, identifier)
    if not item: raise DomainError('用户不存在', 404)
    store.update(item, values)
    return user_view(item)

def health(db, auth_mode):
    store.healthy(db)
    return {'status': 'ok', 'auth_mode': auth_mode, 'currency': 'CNY'}

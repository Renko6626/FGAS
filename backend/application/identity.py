from datetime import datetime, timezone
from backend.infrastructure import store
from backend.kernel.accounting import DomainError

def user_view(user): return dict(id=user.id, display_name=user.display_name, role=user.role, active=user.active)
def admin_user_view(user):
    return dict(user_view(user), sso_subject=user.sso_subject, sso_username=user.sso_username, email=user.email,
                last_login_at=user.last_login_at, created_at=user.created_at,
                source='casdoor' if user.sso_subject else 'development')
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
    user.last_login_at = datetime.now(timezone.utc)
    return user_view(user), store.create_session(db, user.id)
def session_for(db, user): return user_view(user), store.create_session(db, user.id)

def logout(db, token): store.delete_session(db, token)
def users(db, actor):
    require_admin(actor)
    return [admin_user_view(u) for u in store.users(db)]

def update_user(db, actor, identifier, values):
    store.lock(db)
    store.refresh(db, actor)
    require_admin(actor)
    if not actor.active: raise DomainError('用户已停用', 403)
    item = store.get_user(db, identifier)
    if not item: raise DomainError('用户不存在', 404)
    loses_admin = item.role == 'admin' and item.active and (
        ('role' in values and values['role'] != 'admin') or values.get('active') is False)
    if loses_admin and store.other_active_admin_count(db, item.id) == 0:
        raise DomainError('至少保留一名启用中的管理员', 409)
    store.update(item, values)
    if values.get('active') is False: store.delete_sessions_for_user(db, item.id)
    db.flush()
    return admin_user_view(item)

def force_logout(db, actor, identifier):
    store.lock(db)
    store.refresh(db, actor)
    require_admin(actor)
    item = store.get_user(db, identifier)
    if not item: raise DomainError('用户不存在', 404)
    revoked = store.delete_sessions_for_user(db, item.id)
    return dict(ok=True, revoked=revoked, self=item.id == actor.id)

def health(db, auth_mode):
    store.healthy(db)
    return {'status': 'ok', 'auth_mode': auth_mode, 'currency': 'CNY'}

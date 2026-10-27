"""Server-built Agent identity and fixed access levels, separate from human sessions."""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import secrets
from typing import Literal

from backend.infrastructure import agent_store, store
from backend.infrastructure.models import AgentCredential, User
from backend.kernel.accounting import DomainError


@dataclass(frozen=True)
class AgentAccess:
    user: User
    credential_id: str
    credential_name: str
    level: Literal['low', 'high']


def generate_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(secret: str) -> str:
    return sha256(secret.encode('utf-8')).hexdigest()


def require_issue_level(user: User, level: str) -> None:
    if level not in ('low', 'high'):
        raise DomainError('连接权限等级无效')
    if not user.active or user.role not in ('untrusted', 'trusted', 'admin'):
        raise DomainError('用户已停用或角色无效', 403)
    if level == 'high' and user.role != 'admin':
        raise DomainError('高权限连接需要管理员权限', 403)


def resolve(db, bearer: str) -> AgentAccess:
    credential = agent_store.get_by_secret_hash(db, hash_secret(bearer)) if bearer else None
    if (credential is None or not credential.active or
            (credential.expires_at is not None and credential.expires_at <= datetime.now(timezone.utc))):
        raise DomainError('连接凭据无效或已过期', 401)
    user = store.get_user(db, credential.owner_user_id)
    if (user is None or not user.active or
            user.role not in ('untrusted', 'trusted', 'admin') or
            (credential.level == 'high' and user.role != 'admin') or
            credential.level not in ('low', 'high')):
        raise DomainError('连接所属用户已失去授权', 403)
    return AgentAccess(user, credential.id, credential.name, credential.level)


def require_high(access: AgentAccess) -> None:
    if access.level != 'high' or not access.user.active or access.user.role != 'admin':
        raise DomainError('当前连接不能直接办理，需要有效管理员身份和 high 连接。后续可由具备相应权限的人工登录网页办理，或由用户已授权的 high Agent 使用合法 high MCP 连接办理。', 403)


def validate_actor(user: User, access: AgentAccess | None) -> None:
    if access is not None and (access.user is not user or not user.active):
        raise DomainError('连接与操作用户不匹配', 403)


def auto_apply(user: User, *, access: AgentAccess | None = None,
               submit_mode: Literal['propose', 'direct'] | None = None) -> bool:
    validate_actor(user, access)
    if access is None:
        if submit_mode is not None:
            raise DomainError('提交模式需要连接身份')
        return user.role in ('admin', 'trusted')
    if submit_mode == 'propose':
        return False
    if submit_mode == 'direct':
        require_high(access)
        return True
    raise DomainError('连接提交须明确提议或直接执行')


def require_operator(user: User, access: AgentAccess | None) -> None:
    validate_actor(user, access)
    if access is not None:
        require_high(access)


def operation_fields(access: AgentAccess | None) -> dict:
    if access is None:
        return {}
    return dict(agent_credential_id=access.credential_id,
                agent_credential_name=access.credential_name)


def source_fields(access: AgentAccess | None) -> dict:
    if access is None:
        return {}
    return dict(submitted_credential_id=access.credential_id,
                submitted_credential_name=access.credential_name)


def _management_user(db, user: User, *, write=False) -> None:
    if write:
        store.lock(db)
    store.refresh(db, user)
    require_issue_level(user, 'low')


def _credential_view(db, credential: AgentCredential) -> dict:
    owner = store.get_user(db, credential.owner_user_id)
    return dict(id=credential.id, owner_user_id=credential.owner_user_id,
                owner_name=owner.display_name if owner else None,
                name=credential.name, level=credential.level, active=credential.active,
                expires_at=credential.expires_at, created_at=credential.created_at)


def list_credentials(db, user: User) -> list[dict]:
    _management_user(db, user)
    owners = store.users(db) if user.role == 'admin' else [user]
    credentials = [credential for owner in owners
                   for credential in agent_store.list_by_owner(db, owner.id)]
    credentials.sort(key=lambda item: (item.created_at, item.id), reverse=True)
    return [_credential_view(db, credential) for credential in credentials]


def credential_secret(db, user: User, identifier: str) -> dict:
    _management_user(db, user)
    credential = agent_store.get_by_id(db, identifier)
    if credential is None:
        raise DomainError('连接不存在', 404)
    if credential.owner_user_id != user.id:
        raise DomainError('只能查看自己的连接密钥', 403)
    return dict(secret=credential.secret_value)


def _validate_credential_changes(values: dict) -> None:
    if set(values) - {'name', 'level', 'active', 'expires_at'}:
        raise DomainError('连接字段无效')
    if any(values[key] is None for key in ('name', 'level', 'active') if key in values):
        raise DomainError('名称、权限等级和启用状态不能为空')
    if 'name' in values and (not isinstance(values['name'], str) or
                             not values['name'].strip() or len(values['name']) > 200):
        raise DomainError('连接名称须为 1 至 200 个字符')
    expiry = values.get('expires_at')
    if expiry is not None and (not isinstance(expiry, datetime) or
                               expiry.tzinfo is None or expiry.utcoffset() is None):
        raise DomainError('过期时间必须包含时区')
    if 'active' in values and not isinstance(values['active'], bool):
        raise DomainError('启用状态无效')


def create_credential(db, user: User, data: dict) -> dict:
    _management_user(db, user, write=True)
    _validate_credential_changes(data)
    if 'active' in data or 'name' not in data:
        raise DomainError('创建连接字段无效')
    level = data.get('level', 'low')
    require_issue_level(user, level)
    secret = generate_secret()
    credential = agent_store.save(db, AgentCredential(
        owner_user_id=user.id, name=data['name'].strip(), level=level,
        active=True, expires_at=data.get('expires_at'), secret_hash=hash_secret(secret), secret_value=secret))
    return dict(credential=_credential_view(db, credential), secret=secret)


def update_credential(db, user: User, identifier: str, changes: dict) -> dict:
    _management_user(db, user, write=True)
    credential = agent_store.get_by_id(db, identifier)
    if credential is None:
        raise DomainError('连接不存在', 404)
    if credential.owner_user_id != user.id:
        if user.role != 'admin' or changes != {'active': False}:
            raise DomainError('只能停用其他用户的连接', 403)
    else:
        _validate_credential_changes(changes)
        require_issue_level(user, changes.get('level', credential.level))
    values = dict(changes)
    if 'name' in values:
        values['name'] = values['name'].strip()
    store.update(credential, values)
    agent_store.save(db, credential)
    return _credential_view(db, credential)

"""Cohesive persistence adapter for identity, catalogs and funds."""
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text, func, delete, inspect, or_, cast, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import aliased
from backend.infrastructure import auth_config
from backend.infrastructure.database import DATABASE_URL, Session, engine
from backend.infrastructure.models import Base, User, LoginSession, FundAccount, StockAccount, Transfer, JournalLine, Audit, Member

def transaction():
    with Session() as db:
        with db.begin():
            yield db

def lock(db): db.execute(text('SELECT pg_advisory_xact_lock(734621)'))
def healthy(db): db.execute(text('SELECT 1'))
def get_user(db, identifier): return db.get(User, identifier)
def get_account(db, identifier): return db.get(FundAccount, identifier)
def get_stock_account(db, identifier): return db.get(StockAccount, identifier)
def get_transfer(db, identifier): return db.get(Transfer, identifier)
def refresh(db, item): db.refresh(item)
def update(item, values):
    for key, value in values.items(): setattr(item, key, value)
def users(db, active_only=False):
    query = select(User)
    if active_only: query = query.where(User.active.is_(True)).order_by(User.display_name)
    return list(db.scalars(query))
def user_by_sso_subject(db, subject):
    return db.scalar(select(User).where(User.sso_subject == subject))

def session_user(db, token):
    session = db.get(LoginSession, token) if token else None
    if not session or session.expires_at <= datetime.now(timezone.utc): return None
    return get_user(db, session.user_id)

def create_session(db, user_id):
    now = datetime.now(timezone.utc)
    db.execute(delete(LoginSession).where(LoginSession.expires_at <= now))
    session = LoginSession(id=secrets.token_urlsafe(32), user_id=user_id, expires_at=now + auth_config.session_ttl())
    db.add(session); db.flush()
    return session.id

def delete_session(db, token):
    session = db.get(LoginSession, token) if token else None
    if session: db.delete(session)

def delete_sessions_for_user(db, user_id):
    result = db.execute(delete(LoginSession).where(LoginSession.user_id == user_id))
    return result.rowcount or 0

def other_active_admin_count(db, user_id):
    return int(db.scalar(select(func.count()).select_from(User).where(
        User.role == 'admin', User.active.is_(True), User.id != user_id)))

def accounts(db, tag=None, kind=None, member_id=None):
    return catalog_items(db, FundAccount, tag, kind, member_id)
def stock_accounts(db, tag=None, kind=None, member_id=None):
    return catalog_items(db, StockAccount, tag, kind, member_id)
def catalog_items(db, model, tag, kind, member_id):
    query = select(model).order_by(model.name, model.id)
    if kind: query = query.where(model.kind == kind)
    if member_id: query = query.where(model.member_id == member_id)
    return [a for a in db.scalars(query) if tag is None or tag in a.tags]
def create_account(db, values):
    item = FundAccount(**values); db.add(item); db.flush(); return item
def create_stock_account(db, values):
    item = StockAccount(**values); db.add(item); db.flush(); return item

def existing_reversal(db, identifier):
    return db.scalar(select(Transfer).where(Transfer.reversal_of == identifier, Transfer.status.in_(['pending', 'posted'])))
def create_transfer(db, values):
    item = Transfer(**values); db.add(item); db.flush()
    return item

def add_journal(db, transfer_id, line):
    db.add(JournalLine(transfer_id=transfer_id, account_id=line.account_id, debit_minor=line.debit_minor, credit_minor=line.credit_minor))
def audit(db, transfer_id, actor_id, action, detail='', *, access=None):
    db.add(Audit(transfer_id=transfer_id, actor_id=actor_id, action=action, detail=detail,
                 agent_credential_id=access.credential_id if access else None,
                 agent_credential_name=access.credential_name if access else None))
def flush(db): db.flush()
def transfers(db, status=None):
    query = select(Transfer).order_by(Transfer.created_at.desc())
    if status: query = query.where(Transfer.status == status)
    return list(db.scalars(query))
def transfer_page(db, *, status=None, tag=None, q=None, date_from=None, date_to=None, sort='created_at', page=1, limit=20):
    source, destination, actor = aliased(FundAccount), aliased(FundAccount), aliased(User)
    query = (select(Transfer)
             .join(source, Transfer.source_account_id == source.id)
             .join(destination, Transfer.destination_account_id == destination.id)
             .join(actor, Transfer.actor_id == actor.id))
    if status: query = query.where(Transfer.status == status)
    if tag: query = query.where(cast(Transfer.tags, JSONB).contains([tag]))
    if date_from: query = query.where(Transfer.effective_date >= date_from)
    if date_to: query = query.where(Transfer.effective_date <= date_to)
    if q:
        pattern = f'%{q}%'
        query = query.where(or_(source.name.ilike(pattern), destination.name.ilike(pattern),
                                Transfer.description.ilike(pattern), Transfer.counterparty.ilike(pattern),
                                actor.display_name.ilike(pattern), cast(cast(Transfer.tags, JSONB), String).ilike(pattern)))
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    order = Transfer.effective_date.desc() if sort == 'effective_date' else Transfer.created_at.desc()
    items = list(db.scalars(query.order_by(order, Transfer.id.desc()).offset((page - 1) * limit).limit(limit)))
    return items, total
def schema_revision(db):
    if db.scalar(text("SELECT to_regclass('public.alembic_version')")) is None: return None
    return db.scalar(text('SELECT version_num FROM alembic_version'))
def balance_delta(db, identifier, as_of=None, basis='posted'):
    statement = select(func.coalesce(func.sum(JournalLine.debit_minor - JournalLine.credit_minor), 0)).where(JournalLine.account_id == identifier)
    if as_of is not None:
        statement = statement.join(Transfer, Transfer.id == JournalLine.transfer_id)
        if basis == 'posted':
            statement = statement.where(Transfer.posted_at.is_not(None), Transfer.posted_at <= as_of)
        elif basis == 'effective_date':
            statement = statement.where(Transfer.effective_date <= as_of.date())
        else:
            raise ValueError('未知的 as-of 基准')
    return int(db.scalar(statement))
def journal(db, identifier):
    return [dict(account_id=l.account_id, debit_minor=l.debit_minor, credit_minor=l.credit_minor) for l in db.scalars(select(JournalLine).where(JournalLine.transfer_id == identifier))]
def audit_events(db, identifier):
    return [dict(actor_id=a.actor_id, action=a.action, detail=a.detail, created_at=a.created_at, agent_credential_id=a.agent_credential_id, agent_credential_name=a.agent_credential_name) for a in db.scalars(select(Audit).where(Audit.transfer_id == identifier).order_by(Audit.created_at))]
def fund_balances(db, as_of=None, basis='posted'):
    return [dict(id=a.id, name=a.name, kind=a.kind, tags=a.tags, balance_minor=balance_delta(db, a.id, as_of=as_of, basis=basis))
            for a in accounts(db, kind='public')]

RETIRED_TABLES = {'alembic_version','ledger_accounts','stock_locations','stock_location_profiles','location_custodies',
                  'member_claims','repayments','repayment_allocations','stock_operations',
                  'stock_differences','stock_difference_adjustments'}

def alembic_config():
    config = Config(str(Path(__file__).resolve().parents[2] / 'alembic.ini'))
    config.attributes['db_url'] = DATABASE_URL
    return config

def upgrade_schema():
    with engine.connect() as db:
        existing = set(inspect(db).get_table_names())
    known = existing & (set(Base.metadata.tables) | RETIRED_TABLES)
    if known and 'alembic_version' not in existing:
        raise RuntimeError('Unversioned FGAS database; back up and adopt or rebuild it before starting')
    command.upgrade(alembic_config(), 'head')

def reset_schema():
    # Explicit development reset includes retired models, never unrelated tables.
    from sqlalchemy import MetaData
    with engine.begin() as db:
        names = set(inspect(db).get_table_names()) & (set(Base.metadata.tables) | RETIRED_TABLES)
        if names:
            reflected = MetaData()
            reflected.reflect(db, only=list(names))
            unrelated = set(reflected.tables) - names
            if unrelated: raise RuntimeError('Reset encountered non-FGAS dependencies; refusing to drop them')
            reflected.drop_all(db)

def seed_development(admin_id, admin_name):
    with Session.begin() as db:
        for identifier, name, role in [(admin_id, admin_name, 'admin'), ('trusted', '受信任成员', 'trusted'), ('untrusted', '待审批成员', 'untrusted')]:
            if not get_user(db, identifier): db.add(User(id=identifier, display_name=name, role=role, active=True))
        for identifier,name,kind in [('fund_pool','社团资金池','public'),('income','销售收款','external'),('expense','日常支出','external'),('opening','期初','external')]:
            if not get_account(db, identifier): db.add(FundAccount(id=identifier,name=name,kind=kind,tags=['示例']))
        if not get_stock_account(db,'main'): db.add(StockAccount(id='main',name='主存放处',kind='public',tags=['示例']))

def get_member(db, identifier): return db.get(Member, identifier)
def members(db): return list(db.scalars(select(Member).order_by(Member.name,Member.id)))
def create_member(db, values):
    item=Member(**values); db.add(item); db.flush(); return item

@contextmanager
def read_snapshot(db):
    bind = db.get_bind()
    owner = bind.engine if hasattr(bind, 'engine') else bind
    with owner.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
        with connection.begin():
            connection.execute(text('SET TRANSACTION READ ONLY'))
            with Session(bind=connection) as snapshot:
                snapshot.info['snapshot_timestamp'] = snapshot.scalar(text('SELECT transaction_timestamp()'))
                yield snapshot

def snapshot_timestamp(snapshot) -> datetime:
    return snapshot.info['snapshot_timestamp']

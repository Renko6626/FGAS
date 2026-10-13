"""Cohesive persistence adapter for the development identity, catalogs and funds."""
from contextlib import contextmanager
from sqlalchemy import select, text, func
from backend.infrastructure.database import Session, engine
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
def session_user(db, token):
    session = db.get(LoginSession, token) if token else None
    return get_user(db, session.user_id) if session else None

def create_session(db, user_id):
    session = LoginSession(user_id=user_id)
    db.add(session); db.flush()
    return session.id

def delete_session(db, token):
    session = db.get(LoginSession, token) if token else None
    if session: db.delete(session)

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
def audit(db, transfer_id, actor_id, action, detail=''):
    db.add(Audit(transfer_id=transfer_id, actor_id=actor_id, action=action, detail=detail))
def flush(db): db.flush()
def transfers(db, status=None):
    query = select(Transfer).order_by(Transfer.created_at.desc())
    if status: query = query.where(Transfer.status == status)
    return list(db.scalars(query))
def balance_delta(db, identifier):
    return int(db.scalar(select(func.coalesce(func.sum(JournalLine.debit_minor - JournalLine.credit_minor), 0)).where(JournalLine.account_id == identifier)))
def journal(db, identifier):
    return [dict(account_id=l.account_id, debit_minor=l.debit_minor, credit_minor=l.credit_minor) for l in db.scalars(select(JournalLine).where(JournalLine.transfer_id == identifier))]
def audit_events(db, identifier):
    return [dict(actor_id=a.actor_id, action=a.action, detail=a.detail, created_at=a.created_at) for a in db.scalars(select(Audit).where(Audit.transfer_id == identifier).order_by(Audit.created_at))]
def fund_balances(db):
    return [dict(id=a.id, name=a.name, kind=a.kind, tags=a.tags, balance_minor=balance_delta(db,a.id))
            for a in accounts(db, kind='public')]

def create_schema():
    Base.metadata.create_all(engine)

def reset_schema():
    # Explicit development reset includes retired models, never unrelated tables.
    from sqlalchemy import MetaData, inspect
    retired = {'alembic_version','ledger_accounts','stock_locations','stock_location_profiles','location_custodies',
               'member_claims','repayments','repayment_allocations','stock_operations',
               'stock_differences','stock_difference_adjustments'}
    with engine.begin() as db:
        names = set(inspect(db).get_table_names()) & (set(Base.metadata.tables) | retired)
        reflected = MetaData()
        reflected.reflect(db, only=list(names))
        unrelated = set(reflected.tables) - names
        if unrelated: raise RuntimeError('Reset encountered non-FGAS dependencies; refusing to drop them')
        reflected.drop_all(db)
        Base.metadata.create_all(db)

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
            with Session(bind=connection) as snapshot: yield snapshot

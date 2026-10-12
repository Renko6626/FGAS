"""Cohesive persistence adapter for the development identity, catalogs and funds."""
from sqlalchemy import select, text, func
from backend.infrastructure.database import Session, engine
from backend.infrastructure.models import Base, User, LoginSession, Account, FundAccount, Location, Transfer, JournalLine, Audit

def transaction():
    with Session() as db:
        with db.begin():
            yield db

def lock(db): db.execute(text('SELECT pg_advisory_xact_lock(734621)'))
def healthy(db): db.execute(text('SELECT 1'))
def get_user(db, identifier): return db.get(User, identifier)
def get_account(db, identifier): return db.get(Account, identifier)
def get_location(db, identifier): return db.get(Location, identifier)
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

def accounts(db, tag=None):
    return [a for a in db.scalars(select(Account).order_by(Account.name)) if tag is None or tag in a.tags]
def locations(db, tag=None):
    return [l for l in db.scalars(select(Location).order_by(Location.name)) if tag is None or tag in l.tags]
def create_account(db, values, is_fund):
    item = Account(**values); db.add(item); db.flush()
    if is_fund: db.add(FundAccount(account_id=item.id)); db.flush()
    return item

def create_location(db, values):
    item = Location(**values); db.add(item); db.flush()
    return item

def existing_submission(db, actor_id, key):
    return db.scalar(select(Transfer).where(Transfer.actor_id == actor_id, Transfer.idempotency_key == key))
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
def is_fund(db, identifier): return db.get(FundAccount, identifier) is not None
def journal(db, identifier):
    return [dict(account_id=l.account_id, debit_minor=l.debit_minor, credit_minor=l.credit_minor) for l in db.scalars(select(JournalLine).where(JournalLine.transfer_id == identifier))]
def audit_events(db, identifier):
    return [dict(actor_id=a.actor_id, action=a.action, detail=a.detail, created_at=a.created_at) for a in db.scalars(select(Audit).where(Audit.transfer_id == identifier).order_by(Audit.created_at))]
def fund_balances(db):
    # One statement captures all fund balances in a consistent PostgreSQL snapshot.
    rows = db.execute(text("SELECT a.id,a.name,a.kind,a.tags,COALESCE(SUM(j.debit_minor-j.credit_minor),0) AS balance_minor FROM ledger_accounts a JOIN fund_accounts f ON f.account_id=a.id LEFT JOIN journal_lines j ON j.account_id=a.id GROUP BY a.id ORDER BY a.name")).mappings().all()
    return [dict(r, balance_minor=int(r['balance_minor']), is_fund=True) for r in rows]

def create_schema():
    Base.metadata.create_all(engine)

def reset_schema():
    Base.metadata.drop_all(engine)
    create_schema()

def seed_development(admin_id, admin_name):
    with Session.begin() as db:
        for identifier, name, role in [(admin_id, admin_name, 'admin'), ('trusted', '受信任成员', 'trusted'), ('untrusted', '待审批成员', 'untrusted')]:
            if not get_user(db, identifier): db.add(User(id=identifier, display_name=name, role=role, active=True))
        for identifier, name, kind, fund in [('fund_pool', '社团资金池', 'asset', True), ('income', '其它收入', 'income', False), ('expense', '其它费用', 'expense', False), ('opening', '期初权益', 'equity', False)]:
            if not get_account(db, identifier):
                db.add(Account(id=identifier, name=name, kind=kind, tags=['示例'])); db.flush()
                if fund: db.add(FundAccount(account_id=identifier))
        if not get_location(db, 'main'): db.add(Location(id='main', name='主存放处', custodian_label='', tags=['示例']))

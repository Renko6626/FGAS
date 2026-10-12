import os
from fastapi import FastAPI, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from backend.infrastructure.database import Session
from backend.infrastructure.models import User, LoginSession, Account, FundAccount, Location, Transfer
from backend.kernel.accounting import DomainError
from backend.application import funds
from backend.entrypoints.schemas import *

app = FastAPI(title='FGAS development funds prototype')
AUTH_MODE = os.getenv('AUTH_MODE', '')
@app.on_event('startup')
def check_mode():
    if AUTH_MODE != 'development': raise RuntimeError('Only explicit AUTH_MODE=development is available in this prototype')
@app.exception_handler(DomainError)
async def domain_error(request, exc): return JSONResponse(status_code=exc.status, content={'detail': str(exc)})
def database():
    with Session() as db:
        with db.begin(): yield db

def identity(request: Request, db=Depends(database)):
    token = request.cookies.get('fgas_session')
    session = db.get(LoginSession, token) if token else None
    user = db.get(User, session.user_id) if session else None
    if not user or not user.active: raise DomainError('请先登录', 401)
    return user

def admin(user=Depends(identity)):
    if user.role != 'admin': raise DomainError('需要管理员权限', 403)
    return user

def catalog_user(user=Depends(identity)):
    funds.require_trusted(user)
    return user

def user_view(user): return dict(id=user.id, display_name=user.display_name, role=user.role, active=user.active)
def location_view(item): return dict(id=item.id, name=item.name, custodian_label=item.custodian_label, tags=item.tags)
@app.get('/api/health')
def health(db=Depends(database)):
    db.execute(text('SELECT 1'))
    return {'status': 'ok', 'auth_mode': AUTH_MODE, 'currency': 'CNY'}
@app.get('/api/auth/users')
def login_users(db=Depends(database)):
    return [user_view(u) for u in db.scalars(select(User).where(User.active.is_(True)).order_by(User.display_name))]
@app.post('/api/auth/login')
def login(data: Login, response: Response, db=Depends(database)):
    user = db.get(User, data.user_id)
    if not user or not user.active: raise DomainError('用户不存在或已停用', 403)
    session = LoginSession(user_id=user.id)
    db.add(session); db.flush()
    response.set_cookie('fgas_session', session.id, httponly=True, samesite='lax', secure=os.getenv('COOKIE_SECURE', 'false') == 'true')
    return user_view(user)
@app.post('/api/auth/logout')
def logout(request: Request, response: Response, db=Depends(database)):
    token = request.cookies.get('fgas_session')
    session = db.get(LoginSession, token) if token else None
    if session: db.delete(session)
    response.delete_cookie('fgas_session')
    return {'ok': True}
@app.get('/api/auth/me')
def me(user=Depends(identity)): return user_view(user)
@app.get('/api/users')
def users(user=Depends(admin), db=Depends(database)): return [user_view(u) for u in db.scalars(select(User))]
@app.patch('/api/users/{identifier}')
def update_user(identifier: str, data: UserPatch, user=Depends(admin), db=Depends(database)):
    funds.lock(db)
    item = db.get(User, identifier)
    if not item: raise DomainError('用户不存在', 404)
    for key, value in data.model_dump(exclude_none=True).items(): setattr(item, key, value)
    return user_view(item)
@app.get('/api/accounts')
def accounts(tag: str | None=None, user=Depends(identity), db=Depends(database)):
    return [funds.account_view(db, a) for a in db.scalars(select(Account).order_by(Account.name)) if tag is None or tag in a.tags]
@app.post('/api/accounts', status_code=201)
def create_account(data: AccountCreate, user=Depends(catalog_user), db=Depends(database)):
    if data.is_fund and data.kind != 'asset': raise DomainError('资金账户须为资产类')
    item = Account(**data.model_dump(exclude={'is_fund'})); db.add(item); db.flush()
    if data.is_fund: db.add(FundAccount(account_id=item.id)); db.flush()
    return funds.account_view(db, item)
@app.patch('/api/accounts/{identifier}')
def patch_account(identifier: str, data: AccountPatch, user=Depends(catalog_user), db=Depends(database)):
    item = db.get(Account, identifier)
    if not item: raise DomainError('记账对象不存在', 404)
    for key, value in data.model_dump(exclude_none=True).items(): setattr(item, key, value)
    return funds.account_view(db, item)
@app.get('/api/locations')
def locations(tag: str | None=None, user=Depends(identity), db=Depends(database)):
    return [location_view(l) for l in db.scalars(select(Location).order_by(Location.name)) if tag is None or tag in l.tags]
@app.post('/api/locations', status_code=201)
def create_location(data: LocationCreate, user=Depends(catalog_user), db=Depends(database)):
    item = Location(**data.model_dump()); db.add(item); db.flush()
    return location_view(item)
@app.patch('/api/locations/{identifier}')
def patch_location(identifier: str, data: LocationPatch, user=Depends(catalog_user), db=Depends(database)):
    item = db.get(Location, identifier)
    if not item: raise DomainError('位置不存在', 404)
    for key, value in data.model_dump(exclude_none=True).items(): setattr(item, key, value)
    return location_view(item)
@app.post('/api/transfers/preview')
def preview(data: Preview, user=Depends(identity), db=Depends(database)):
    lines = funds.validate(db, data.source_account_id, data.destination_account_id, data.amount)
    return {'amount_minor': lines[0].credit_minor, 'status': 'pending' if user.role == 'untrusted' else 'posted', 'source_account_name': db.get(Account, data.source_account_id).name, 'destination_account_name': db.get(Account, data.destination_account_id).name, 'journal_lines': [vars(l) for l in lines]}
@app.post('/api/transfers', status_code=201)
def submit(data: Submit, user=Depends(identity), db=Depends(database)):
    return funds.transfer_view(db, funds.submit(db, user, data.model_dump(mode='json')), True)
@app.get('/api/transfers')
def transfers(status: str | None=None, user=Depends(identity), db=Depends(database)):
    query = select(Transfer).order_by(Transfer.created_at.desc())
    if status: query = query.where(Transfer.status == status)
    return [funds.transfer_view(db, t) for t in db.scalars(query)]
@app.get('/api/transfers/{identifier}')
def detail(identifier: str, user=Depends(identity), db=Depends(database)):
    return funds.transfer_view(db, funds.get_transfer(db, identifier), True)
@app.post('/api/transfers/{identifier}/approve')
def approve(identifier: str, data: Approval, user=Depends(identity), db=Depends(database)):
    return funds.transfer_view(db, funds.decide(db, user, identifier, data.expected_version), True)
@app.post('/api/transfers/{identifier}/reject')
def reject(identifier: str, data: Rejection, user=Depends(identity), db=Depends(database)):
    return funds.transfer_view(db, funds.decide(db, user, identifier, data.expected_version, data.reason), True)
@app.post('/api/transfers/{identifier}/reverse', status_code=201)
def reverse(identifier: str, data: Reversal, user=Depends(identity), db=Depends(database)):
    original = funds.get_transfer(db, identifier)
    payload = dict(source_account_id=original.destination_account_id, destination_account_id=original.source_account_id, amount=f'{original.amount_minor // 100}.{original.amount_minor % 100:02d}', effective_date=original.effective_date.isoformat(), description=f'冲销：{original.description}', counterparty=original.counterparty, idempotency_key=data.idempotency_key)
    return funds.transfer_view(db, funds.submit(db, user, payload, original.id, data.reason), True)
@app.get('/api/funds/summary')
def summary(user=Depends(identity), db=Depends(database)):
    # One statement captures all fund balances in a consistent PostgreSQL snapshot.
    rows = db.execute(text("SELECT a.id,a.name,a.kind,a.tags,COALESCE(SUM(j.debit_minor-j.credit_minor),0) AS balance_minor FROM ledger_accounts a JOIN fund_accounts f ON f.account_id=a.id LEFT JOIN journal_lines j ON j.account_id=a.id GROUP BY a.id ORDER BY a.name")).mappings().all()
    values = [dict(r, balance_minor=int(r['balance_minor']), is_fund=True) for r in rows]
    return {'accounts': values, 'total_minor': sum(r['balance_minor'] for r in values), 'currency': 'CNY'}

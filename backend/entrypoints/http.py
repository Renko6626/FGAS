import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, Response
from fastapi.responses import JSONResponse
from backend.infrastructure.store import transaction as database
from backend.kernel.accounting import DomainError
from backend.application import funds, catalogs, identity as identities
from backend.entrypoints.schemas import *

AUTH_MODE = os.getenv('AUTH_MODE', '')
@asynccontextmanager
async def lifespan(app):
    if AUTH_MODE != 'development': raise RuntimeError('Only explicit AUTH_MODE=development is available in this prototype')
    yield

app = FastAPI(title='FGAS development funds prototype', lifespan=lifespan)
@app.exception_handler(DomainError)
async def domain_error(request, exc): return JSONResponse(status_code=exc.status, content={'detail': str(exc)})
def identity(request: Request, db=Depends(database)):
    return identities.resolve(db, request.cookies.get('fgas_session'))

@app.get('/api/health')
def health(db=Depends(database)):
    return identities.health(db, AUTH_MODE)
@app.get('/api/auth/users')
def login_users(db=Depends(database)):
    return identities.login_users(db)
@app.post('/api/auth/login')
def login(data: Login, response: Response, db=Depends(database)):
    user, token = identities.login(db, data.user_id)
    response.set_cookie('fgas_session', token, httponly=True, samesite='lax', secure=os.getenv('COOKIE_SECURE', 'false') == 'true')
    return user
@app.post('/api/auth/logout')
def logout(request: Request, response: Response, db=Depends(database)):
    identities.logout(db, request.cookies.get('fgas_session'))
    response.delete_cookie('fgas_session')
    return {'ok': True}
@app.get('/api/auth/me')
def me(user=Depends(identity)): return identities.user_view(user)
@app.get('/api/users')
def users(user=Depends(identity), db=Depends(database)):
    return identities.users(db, user)
@app.patch('/api/users/{identifier}')
def update_user(identifier: str, data: UserPatch, user=Depends(identity), db=Depends(database)):
    return identities.update_user(db, user, identifier, data.model_dump(exclude_none=True))
@app.get('/api/accounts')
def accounts(tag: str | None=None, user=Depends(identity), db=Depends(database)):
    return catalogs.accounts(db, tag)
@app.post('/api/accounts', status_code=201)
def create_account(data: AccountCreate, user=Depends(identity), db=Depends(database)):
    return catalogs.create_account(db, user, data.model_dump())
@app.patch('/api/accounts/{identifier}')
def patch_account(identifier: str, data: AccountPatch, user=Depends(identity), db=Depends(database)):
    return catalogs.update_account(db, user, identifier, data.model_dump(exclude_none=True))
@app.get('/api/locations')
def locations(tag: str | None=None, user=Depends(identity), db=Depends(database)):
    return catalogs.locations(db, tag)
@app.post('/api/locations', status_code=201)
def create_location(data: LocationCreate, user=Depends(identity), db=Depends(database)):
    return catalogs.create_location(db, user, data.model_dump())
@app.patch('/api/locations/{identifier}')
def patch_location(identifier: str, data: LocationPatch, user=Depends(identity), db=Depends(database)):
    return catalogs.update_location(db, user, identifier, data.model_dump(exclude_none=True))
@app.post('/api/transfers/preview')
def preview(data: Preview, user=Depends(identity), db=Depends(database)):
    return funds.preview(db, user, data.model_dump(mode='json'))
@app.post('/api/transfers', status_code=201)
def submit(data: Submit, user=Depends(identity), db=Depends(database)):
    return funds.transfer_view(db, funds.submit(db, user, data.model_dump(mode='json')), True)
@app.get('/api/transfers')
def transfers(status: str | None=None, user=Depends(identity), db=Depends(database)):
    return funds.list_transfers(db, status)
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
    return funds.reverse(db, user, identifier, data.reason, data.idempotency_key)
@app.get('/api/funds/summary')
def summary(user=Depends(identity), db=Depends(database)):
    return funds.summary(db)

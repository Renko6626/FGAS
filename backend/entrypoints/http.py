import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, Response
from fastapi.responses import JSONResponse
from backend.infrastructure.store import transaction as database
from backend.kernel.accounting import DomainError
from backend.application import funds, catalogs, warehouse_catalogs, member_claims, identity as identities
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
    return catalogs.update_location(db, user, identifier, data.model_dump(exclude_unset=True))
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
    return funds.reverse(db, user, identifier, data.reason)
@app.get('/api/funds/summary')
def summary(user=Depends(identity), db=Depends(database)):
    return funds.summary(db)

@app.get('/api/members')
def members(user=Depends(identity), db=Depends(database)):
    return member_claims.list_members(db)
@app.post('/api/members', status_code=201)
def create_member(data: MemberCreate, user=Depends(identity), db=Depends(database)):
    return member_claims.create_member(db, user, data.model_dump())
@app.patch('/api/members/{identifier}')
def patch_member(identifier: str, data: MemberPatch, user=Depends(identity), db=Depends(database)):
    return member_claims.update_member(db, user, identifier, data.model_dump(exclude_none=True))

@app.get('/api/member-claims')
def claims(member_id: str | None=None, status: str | None=None, user=Depends(identity), db=Depends(database)):
    return member_claims.list_claims(db, member_id, status)
@app.post('/api/member-claims', status_code=201)
def submit_claim(data: ClaimSubmit, user=Depends(identity), db=Depends(database)):
    return member_claims.submit_claim(db, user, data.model_dump(mode='json'))
@app.get('/api/member-claims/{identifier}')
def claim_detail(identifier: str, user=Depends(identity), db=Depends(database)):
    return member_claims.get_claim(db, identifier)
@app.post('/api/member-claims/{identifier}/confirm')
def confirm_claim(identifier: str, data: ClaimConfirmation, user=Depends(identity), db=Depends(database)):
    return member_claims.confirm_claim(db, user, identifier, data.expected_version, data.confirmed_amount, data.confirmation_reason)
@app.post('/api/member-claims/{identifier}/reject')
def reject_claim(identifier: str, data: Rejection, user=Depends(identity), db=Depends(database)):
    return member_claims.reject_claim(db, user, identifier, data.expected_version, data.reason)

@app.post('/api/repayments/preview')
def preview_repayment(data: RepaymentPreview, user=Depends(identity), db=Depends(database)):
    return member_claims.preview_repayment(db, user, data.model_dump(mode='json'))
@app.post('/api/repayments', status_code=201)
def submit_repayment(data: RepaymentSubmit, user=Depends(identity), db=Depends(database)):
    return member_claims.submit_repayment(db, user, data.model_dump(mode='json'))
@app.get('/api/repayments')
def repayments(member_id: str | None=None, user=Depends(identity), db=Depends(database)):
    return member_claims.list_repayments(db, member_id)
@app.get('/api/repayments/{identifier}')
def repayment_detail(identifier: str, user=Depends(identity), db=Depends(database)):
    return member_claims.get_repayment(db, identifier)


@app.get('/api/members/{identifier}')
def member_detail(identifier: str, user=Depends(identity), db=Depends(database)):
    return member_claims.member_detail(db, identifier)


@app.get('/api/skus')
def skus(user=Depends(identity), db=Depends(database)):
    return warehouse_catalogs.skus(db)
@app.post('/api/skus', status_code=201)
def create_sku(data: SkuCreate, user=Depends(identity), db=Depends(database)):
    return warehouse_catalogs.create_sku(db, user, data.model_dump())
@app.patch('/api/skus/{identifier}')
def patch_sku(identifier: str, data: SkuPatch, user=Depends(identity), db=Depends(database)):
    return warehouse_catalogs.update_sku(db, user, identifier, data.model_dump(exclude_unset=True))
@app.post('/api/locations/{identifier}/custody')
def set_custody(identifier: str, data: CustodyInput, user=Depends(identity), db=Depends(database)):
    return warehouse_catalogs.set_custody(db, user, identifier, data.member_id)

from backend.application import warehouse

@app.post('/api/stock-transfers', status_code=201)
def submit_stock_transfer(data: StockTransferInput, user=Depends(identity), db=Depends(database)):
    return warehouse.submit_transfer(db, user, data.model_dump(mode='json'))
@app.get('/api/stock-transfers')
def stock_transfers(status: str | None=None, action_kind: str | None=None, source_location_id: str | None=None, destination_location_id: str | None=None, sku_id: str | None=None, user=Depends(identity), db=Depends(database)):
    return warehouse.list_transfers(db, status, dict(action_kind=action_kind,source_location_id=source_location_id,destination_location_id=destination_location_id,sku_id=sku_id))
@app.get('/api/stock-transfers/{identifier}')
def stock_transfer_detail(identifier: str, user=Depends(identity), db=Depends(database)):
    return warehouse.transfer_detail(db, identifier)
@app.post('/api/stock-transfers/{identifier}/approve')
def approve_stock_transfer(identifier: str, data: StockApproval, user=Depends(identity), db=Depends(database)):
    return warehouse.decide_transfer(db, user, identifier, data.model_dump(mode='json'))
@app.post('/api/stock-transfers/{identifier}/reject')
def reject_stock_transfer(identifier: str, data: StockRejection, user=Depends(identity), db=Depends(database)):
    return warehouse.decide_transfer(db, user, identifier, data.model_dump(mode='json'), rejection=True)
@app.post('/api/stock-transfers/{identifier}/cancel')
def cancel_stock_transfer(identifier: str, data: StockRejection, user=Depends(identity), db=Depends(database)):
    return warehouse.cancel_transfer(db, user, identifier, data.model_dump(mode='json'))

@app.post('/api/stock-transfers/{identifier}/completion')
def complete_stock_transfer(identifier: str, data: CompletionInput, user=Depends(identity), db=Depends(database)):
    return warehouse.request_completion(db, user, identifier, data.model_dump(mode='json'))
@app.post('/api/stock-confirmations/{identifier}/approve')
def approve_stock_completion(identifier: str, data: StockApproval, user=Depends(identity), db=Depends(database)):
    return warehouse.decide_completion(db, user, identifier, data.model_dump(mode='json'))
@app.post('/api/stock-confirmations/{identifier}/reject')
def reject_stock_completion(identifier: str, data: StockRejection, user=Depends(identity), db=Depends(database)):
    return warehouse.decide_completion(db, user, identifier, data.model_dump(mode='json'), rejection=True)
@app.get('/api/inventory')
def stock_inventory(sku_id: str | None=None, location_id: str | None=None, member_id: str | None=None, user=Depends(identity), db=Depends(database)):
    return warehouse.inventory(db, dict(sku_id=sku_id, location_id=location_id, member_id=member_id))
@app.get('/api/stock-moves')
def stock_moves(sku_id: str | None=None, source_location_id: str | None=None, destination_location_id: str | None=None, transfer_id: str | None=None, user=Depends(identity), db=Depends(database)):
    return warehouse.list_moves(db,dict(sku_id=sku_id,source_location_id=source_location_id,destination_location_id=destination_location_id,transfer_id=transfer_id))

@app.post('/api/stock-transfers/{identifier}/fund-references')
def add_stock_fund_reference(identifier: str, data: StockFundReferenceInput, user=Depends(identity), db=Depends(database)):
    return warehouse.add_fund_reference(db, user, identifier, data.model_dump(mode='json'))

@app.post('/api/stock-operations', status_code=201)
def submit_stock_operation(data: StockOperationInput, user=Depends(identity), db=Depends(database)):
    from backend.application.stock_workflows import submit_stock_with_money
    return submit_stock_with_money(db, user, data.model_dump(mode='json'))

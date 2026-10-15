import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, Response
from fastapi.responses import JSONResponse
from backend.infrastructure.store import transaction as database
from backend.kernel.accounting import DomainError
from backend.application import funds, catalogs, warehouse_catalogs, members as member_service, settlements, identity as identities
from backend.entrypoints.schemas import *
from backend.entrypoints.agent_schemas import CredentialCreate, CredentialPatch
from backend.application import agent_access
from backend.entrypoints.mcp import create_mcp_app

mcp_app = create_mcp_app()

AUTH_MODE = os.getenv('AUTH_MODE', '')
@asynccontextmanager
async def lifespan(app):
    if AUTH_MODE != 'development': raise RuntimeError('Only explicit AUTH_MODE=development is available in this prototype')
    global mcp_app
    previous = mcp_app
    current = create_mcp_app()
    mcp_app = mcp_mount.app = current
    try:
        async with current.session_manager.run():
            yield
    finally:
        mcp_app = mcp_mount.app = previous

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
@app.get('/api/agent-credentials')
def agent_credentials(user=Depends(identity), db=Depends(database)):
    return agent_access.list_credentials(db, user)
@app.post('/api/agent-credentials')
def create_agent_credential(data: CredentialCreate, user=Depends(identity), db=Depends(database)):
    return agent_access.create_credential(db, user, data.model_dump())
@app.patch('/api/agent-credentials/{identifier}')
def patch_agent_credential(identifier: str, data: CredentialPatch, user=Depends(identity), db=Depends(database)):
    return agent_access.update_credential(db, user, identifier, data.model_dump(exclude_unset=True))

@app.get('/api/accounts')
def accounts(tag: str | None=None, kind: str | None=None, member_id: str | None=None, user=Depends(identity), db=Depends(database)):
    return catalogs.accounts(db, tag, kind, member_id)
@app.post('/api/accounts', status_code=201)
def create_account(data: AccountCreate, user=Depends(identity), db=Depends(database)):
    return catalogs.create_account(db, user, data.model_dump())
@app.patch('/api/accounts/{identifier}')
def patch_account(identifier: str, data: AccountPatch, user=Depends(identity), db=Depends(database)):
    return catalogs.update_account(db, user, identifier, data.model_dump(exclude_unset=True))
@app.get('/api/stock-accounts')
def stock_accounts(tag: str | None=None, kind: str | None=None, member_id: str | None=None, user=Depends(identity), db=Depends(database)):
    return catalogs.stock_accounts(db, tag, kind, member_id)
@app.post('/api/stock-accounts', status_code=201)
def create_location(data: AccountCreate, user=Depends(identity), db=Depends(database)):
    return catalogs.create_stock_account(db, user, data.model_dump())
@app.patch('/api/stock-accounts/{identifier}')
def patch_location(identifier: str, data: AccountPatch, user=Depends(identity), db=Depends(database)):
    return catalogs.update_stock_account(db, user, identifier, data.model_dump(exclude_unset=True))
@app.post('/api/transfers/preview')
def preview(data: Preview, user=Depends(identity), db=Depends(database)):
    return funds.preview(db, user, data.model_dump(mode='json'))
@app.post('/api/transfers', status_code=201)
def submit(data: Submit, user=Depends(identity), db=Depends(database)):
    return funds.transfer_view(db, funds.submit(db, user, data.model_dump(mode='json')), True)
@app.get('/api/transfers')
def transfers(status: str | None=None, tag: str | None=None, user=Depends(identity), db=Depends(database)):
    return funds.list_transfers(db, status, tag)
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
    return member_service.list_members(db)
@app.post('/api/members', status_code=201)
def create_member(data: MemberCreate, user=Depends(identity), db=Depends(database)):
    return member_service.create_member(db, user, data.model_dump())
@app.patch('/api/members/{identifier}')
def patch_member(identifier: str, data: MemberPatch, user=Depends(identity), db=Depends(database)):
    return member_service.update_member(db, user, identifier, data.model_dump(exclude_none=True))

@app.get('/api/accounts/{identifier}/settlement-overview')
def settlement_overview(identifier: str,user=Depends(identity),db=Depends(database)):
    return settlements.overview(db,identifier)
@app.post('/api/settlements',status_code=201)
def create_settlement(data: SettlementCreate,user=Depends(identity),db=Depends(database)):
    return settlements.create(db,user,data.model_dump(mode='json'))
@app.post('/api/transfers/{identifier}/settlement-matches',status_code=201)
def add_settlement_matches(identifier: str,data: SettlementMatches,user=Depends(identity),db=Depends(database)):
    return settlements.add_matches(db,user,identifier,data.model_dump()['allocations'])

@app.get('/api/skus')
def skus(user=Depends(identity), db=Depends(database)):
    return warehouse_catalogs.skus(db)
@app.post('/api/skus', status_code=201)
def create_sku(data: SkuCreate, user=Depends(identity), db=Depends(database)):
    return warehouse_catalogs.create_sku(db, user, data.model_dump())
@app.patch('/api/skus/{identifier}')
def patch_sku(identifier: str, data: SkuPatch, user=Depends(identity), db=Depends(database)):
    return warehouse_catalogs.update_sku(db, user, identifier, data.model_dump(exclude_unset=True))
@app.post('/api/stock-accounts/{identifier}/custody')
def set_custody(identifier: str, data: CustodyInput, user=Depends(identity), db=Depends(database)):
    return warehouse_catalogs.set_custody(db, user, identifier, data.member_id)

from backend.application import warehouse

@app.post('/api/stock-transfers', status_code=201)
def submit_stock_transfer(data: StockTransferInput, user=Depends(identity), db=Depends(database)):
    return warehouse.submit_transfer(db, user, data.model_dump(mode='json'))
@app.get('/api/stock-transfers')
def stock_transfers(status: str | None=None, tag: str | None=None, source_account_id: str | None=None, destination_account_id: str | None=None, sku_id: str | None=None, user=Depends(identity), db=Depends(database)):
    return warehouse.list_transfers(db, status, dict(tag=tag,source_account_id=source_account_id,destination_account_id=destination_account_id,sku_id=sku_id))
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
def stock_inventory(sku_id: str | None=None, account_id: str | None=None, member_id: str | None=None, custodian_id: str | None=None, user=Depends(identity), db=Depends(database)):
    return warehouse.inventory(db, dict(sku_id=sku_id, account_id=account_id, member_id=member_id,custodian_id=custodian_id))
@app.get('/api/stock-moves')
def stock_moves(sku_id: str | None=None, source_account_id: str | None=None, destination_account_id: str | None=None, transfer_id: str | None=None, user=Depends(identity), db=Depends(database)):
    return warehouse.list_moves(db,dict(sku_id=sku_id,source_account_id=source_account_id,destination_account_id=destination_account_id,transfer_id=transfer_id))

@app.post('/api/stock-transfers/{identifier}/fund-references')
def add_stock_fund_reference(identifier: str, data: StockFundReferenceInput, user=Depends(identity), db=Depends(database)):
    return warehouse.add_fund_reference(db, user, identifier, data.model_dump(mode='json'))

@app.post('/api/stock-operations', status_code=201)
def submit_stock_operation(data: StockOperationInput, user=Depends(identity), db=Depends(database)):
    from backend.application.stock_workflows import submit_stock_with_money
    return submit_stock_with_money(db, user, data.model_dump(mode='json'))


from backend.application import stocktakes

@app.get('/api/fund-stocktakes')
def list_fund_stocktakes(status: Literal['in_progress', 'ended'] | None=None, user=Depends(identity), db=Depends(database)):
    return stocktakes.list_stocktakes(db, 'fund', status)
@app.post('/api/fund-stocktakes', status_code=201)
def create_fund_stocktake(data: StocktakeCreate, user=Depends(identity), db=Depends(database)):
    return stocktakes.create_stocktake(db, user, 'fund', data.model_dump())
@app.get('/api/fund-stocktakes/{identifier}')
def get_fund_stocktake(identifier: str, user=Depends(identity), db=Depends(database)):
    return stocktakes.get_stocktake(db, 'fund', identifier)
@app.patch('/api/fund-stocktakes/{identifier}')
def patch_fund_stocktake(identifier: str, data: StocktakePatch, user=Depends(identity), db=Depends(database)):
    return stocktakes.update_description(db, user, 'fund', identifier, data.description)
@app.post('/api/fund-stocktakes/{identifier}/end')
def end_fund_stocktake(identifier: str, user=Depends(identity), db=Depends(database)):
    return stocktakes.end_stocktake(db, user, 'fund', identifier)

@app.get('/api/stock-stocktakes')
def list_stock_stocktakes(status: Literal['in_progress', 'ended'] | None=None, user=Depends(identity), db=Depends(database)):
    return stocktakes.list_stocktakes(db, 'stock', status)
@app.post('/api/stock-stocktakes', status_code=201)
def create_stock_stocktake(data: StocktakeCreate, user=Depends(identity), db=Depends(database)):
    return stocktakes.create_stocktake(db, user, 'stock', data.model_dump())
@app.get('/api/stock-stocktakes/{identifier}')
def get_stock_stocktake(identifier: str, user=Depends(identity), db=Depends(database)):
    return stocktakes.get_stocktake(db, 'stock', identifier)
@app.patch('/api/stock-stocktakes/{identifier}')
def patch_stock_stocktake(identifier: str, data: StocktakePatch, user=Depends(identity), db=Depends(database)):
    return stocktakes.update_description(db, user, 'stock', identifier, data.description)
@app.post('/api/stock-stocktakes/{identifier}/end')
def end_stock_stocktake(identifier: str, user=Depends(identity), db=Depends(database)):
    return stocktakes.end_stocktake(db, user, 'stock', identifier)


# Last route: the SDK owns the exact /mcp path without a mount redirect.
app.mount('/', mcp_app)
mcp_mount = app.routes[-1]

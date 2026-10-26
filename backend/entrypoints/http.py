from contextlib import asynccontextmanager
from datetime import date
from typing import Literal
from fastapi import APIRouter, FastAPI, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from backend.infrastructure import auth_config
from backend.infrastructure.store import transaction as database
from backend.kernel.accounting import DomainError
from backend.application import funds, catalogs, warehouse_catalogs, members as member_service, settlements, identity as identities, sso
from backend.entrypoints.schemas import *
from backend.application import agent_access
from backend.application import dashboard
from backend.entrypoints.mcp import create_mcp_app

router = APIRouter()
# Commit before returning success, so the next request sees the saved session or record.
database_dependency = Depends(database, scope="function")

async def domain_error(request, exc): return JSONResponse(status_code=exc.status, content={'detail': str(exc)})
def identity(request: Request, db=database_dependency):
    return identities.resolve(db, request.cookies.get('fgas_session'))
def require_mode(expected):
    if auth_config.auth_mode() != expected: raise HTTPException(status_code=404, detail='Not Found')
def set_session_cookie(response, token):
    response.set_cookie('fgas_session', token, httponly=True, samesite='lax',
                        secure=auth_config.cookie_secure(), max_age=int(auth_config.session_ttl().total_seconds()))

@router.get('/api/health')
def health(db=database_dependency):
    return identities.health(db, auth_config.auth_mode())
@router.get('/api/auth/config')
def auth_config_view():
    return {'mode': auth_config.auth_mode()}
@router.get('/api/auth/users')
def login_users(db=database_dependency):
    require_mode('development')
    return identities.login_users(db)
@router.post('/api/auth/login')
def login(data: Login, response: Response, db=database_dependency):
    require_mode('development')
    user, token = identities.login(db, data.user_id)
    set_session_cookie(response, token)
    return user
@router.get('/api/auth/casdoor/login')
def casdoor_login():
    require_mode('casdoor')
    location, state = sso.begin()
    response = RedirectResponse(location, status_code=303)
    response.set_cookie(sso.STATE_COOKIE, state, max_age=sso.STATE_MAX_AGE, path='/api/auth/casdoor',
                        httponly=True, samesite='lax', secure=auth_config.cookie_secure())
    return response
@router.get('/api/auth/casdoor/callback')
def casdoor_callback(request: Request, code: str | None=None, state: str | None=None, error: str | None=None, db=database_dependency):
    require_mode('casdoor')
    def finish_redirect(reason=None):
        response = RedirectResponse(f'/?sso_error={reason}' if reason else '/', status_code=303)
        response.delete_cookie(sso.STATE_COOKIE, path='/api/auth/casdoor')
        return response
    if error: return finish_redirect('access_denied')
    try:
        user = sso.provision(db, sso.finish(code, state, request.cookies.get(sso.STATE_COOKIE)))
        _, token = identities.session_for(db, user)
    except DomainError as exc:
        reason = {400: 'invalid_state', 403: 'user_disabled', 502: 'idp_unavailable'}.get(exc.status, 'login_failed')
        return finish_redirect(reason)
    response = finish_redirect()
    set_session_cookie(response, token)
    return response
@router.post('/api/auth/logout')
def logout(request: Request, response: Response, db=database_dependency):
    identities.logout(db, request.cookies.get('fgas_session'))
    response.delete_cookie('fgas_session')
    return {'ok': True}
@router.get('/api/auth/me')
def me(user=Depends(identity)): return identities.user_view(user)
@router.get('/api/users')
def users(user=Depends(identity), db=database_dependency):
    return identities.users(db, user)
@router.patch('/api/users/{identifier}')
def update_user(identifier: str, data: UserPatch, response: Response, user=Depends(identity), db=database_dependency):
    item = identities.update_user(db, user, identifier, data.model_dump(exclude_none=True))
    if item['id'] == user.id and not item['active']: response.delete_cookie('fgas_session')
    return item
@router.post('/api/users/{identifier}/logout')
def force_logout(identifier: str, response: Response, user=Depends(identity), db=database_dependency):
    result = identities.force_logout(db, user, identifier)
    if result['self']: response.delete_cookie('fgas_session')
    return result
@router.get('/api/agent-credentials')
def agent_credentials(user=Depends(identity), db=database_dependency):
    return agent_access.list_credentials(db, user)
@router.post('/api/agent-credentials')
def create_agent_credential(data: CredentialCreate, user=Depends(identity), db=database_dependency):
    return agent_access.create_credential(db, user, data.model_dump())
@router.get('/api/agent-credentials/{identifier}/secret')
def agent_credential_secret(identifier: str, response: Response, user=Depends(identity), db=database_dependency):
    response.headers['Cache-Control'] = 'no-store'
    return agent_access.credential_secret(db, user, identifier)
@router.patch('/api/agent-credentials/{identifier}')
def patch_agent_credential(identifier: str, data: CredentialPatch, user=Depends(identity), db=database_dependency):
    return agent_access.update_credential(db, user, identifier, data.model_dump(exclude_unset=True))

@router.get('/api/accounts')
def accounts(tag: str | None=None, kind: str | None=None, member_id: str | None=None, user=Depends(identity), db=database_dependency):
    return catalogs.accounts(db, tag, kind, member_id)
@router.post('/api/accounts', status_code=201)
def create_account(data: AccountCreate, user=Depends(identity), db=database_dependency):
    return catalogs.create_account(db, user, data.model_dump())
@router.patch('/api/accounts/{identifier}')
def patch_account(identifier: str, data: AccountPatch, user=Depends(identity), db=database_dependency):
    return catalogs.update_account(db, user, identifier, data.model_dump(exclude_unset=True))
@router.get('/api/stock-accounts')
def stock_accounts(tag: str | None=None, kind: str | None=None, member_id: str | None=None, user=Depends(identity), db=database_dependency):
    return catalogs.stock_accounts(db, tag, kind, member_id)
@router.post('/api/stock-accounts', status_code=201)
def create_location(data: AccountCreate, user=Depends(identity), db=database_dependency):
    return catalogs.create_stock_account(db, user, data.model_dump())
@router.patch('/api/stock-accounts/{identifier}')
def patch_location(identifier: str, data: AccountPatch, user=Depends(identity), db=database_dependency):
    return catalogs.update_stock_account(db, user, identifier, data.model_dump(exclude_unset=True))
@router.post('/api/transfers/preview')
def preview(data: Preview, user=Depends(identity), db=database_dependency):
    return funds.preview(db, user, data.model_dump(mode='json'))
@router.post('/api/transfers', status_code=201)
def submit(data: Submit, user=Depends(identity), db=database_dependency):
    return funds.transfer_view(db, funds.submit(db, user, data.model_dump(mode='json')), True)
@router.get('/api/transfers')
def transfers(status: str | None=None, tag: str | None=None, q: str | None=None,
              date_from: date | None=None, date_to: date | None=None,
              sort: Literal['created_at', 'effective_date']='created_at',
              page: int=Query(1, ge=1), limit: int=Query(20, ge=1, le=100),
              user=Depends(identity), db=database_dependency):
    return funds.list_transfers(db, status, tag, q, date_from, date_to, sort, page, limit)
@router.get('/api/transfers/{identifier}')
def detail(identifier: str, user=Depends(identity), db=database_dependency):
    return funds.transfer_view(db, funds.get_transfer(db, identifier), True)
@router.post('/api/transfers/{identifier}/approve')
def approve(identifier: str, data: Approval, user=Depends(identity), db=database_dependency):
    return funds.transfer_view(db, funds.decide(db, user, identifier, data.expected_version), True)
@router.post('/api/transfers/{identifier}/reject')
def reject(identifier: str, data: Rejection, user=Depends(identity), db=database_dependency):
    return funds.transfer_view(db, funds.decide(db, user, identifier, data.expected_version, data.reason), True)
@router.post('/api/transfers/{identifier}/reverse', status_code=201)
def reverse(identifier: str, data: Reversal, user=Depends(identity), db=database_dependency):
    return funds.reverse(db, user, identifier, data.reason)
@router.get('/api/funds/summary')
def summary(user=Depends(identity), db=database_dependency):
    return funds.summary(db)

@router.get('/api/dashboard')
def dashboard_overview(user=Depends(identity), db=database_dependency):
    return dashboard.overview(db)

@router.get('/api/members')
def members(user=Depends(identity), db=database_dependency):
    return member_service.list_members(db)
@router.post('/api/members', status_code=201)
def create_member(data: MemberCreate, user=Depends(identity), db=database_dependency):
    return member_service.create_member(db, user, data.model_dump())
@router.patch('/api/members/{identifier}')
def patch_member(identifier: str, data: MemberPatch, user=Depends(identity), db=database_dependency):
    return member_service.update_member(db, user, identifier, data.model_dump(exclude_none=True))

@router.get('/api/accounts/{identifier}/settlement-overview')
def settlement_overview(identifier: str,user=Depends(identity),db=database_dependency):
    return settlements.overview(db,identifier)
@router.post('/api/settlements',status_code=201)
def create_settlement(data: SettlementCreate,user=Depends(identity),db=database_dependency):
    return settlements.create(db,user,data.model_dump(mode='json'))
@router.post('/api/transfers/{identifier}/settlement-matches',status_code=201)
def add_settlement_matches(identifier: str,data: SettlementMatches,user=Depends(identity),db=database_dependency):
    return settlements.add_matches(db,user,identifier,data.model_dump()['allocations'])

@router.get('/api/skus')
def skus(user=Depends(identity), db=database_dependency):
    return warehouse_catalogs.skus(db)
@router.post('/api/skus', status_code=201)
def create_sku(data: SkuCreate, user=Depends(identity), db=database_dependency):
    return warehouse_catalogs.create_sku(db, user, data.model_dump())
@router.patch('/api/skus/{identifier}')
def patch_sku(identifier: str, data: SkuPatch, user=Depends(identity), db=database_dependency):
    return warehouse_catalogs.update_sku(db, user, identifier, data.model_dump(exclude_unset=True))
@router.post('/api/stock-accounts/{identifier}/custody')
def set_custody(identifier: str, data: CustodyInput, user=Depends(identity), db=database_dependency):
    return warehouse_catalogs.set_custody(db, user, identifier, data.member_id)

from backend.application import warehouse

@router.post('/api/stock-transfers', status_code=201)
def submit_stock_transfer(data: StockTransferInput, user=Depends(identity), db=database_dependency):
    return warehouse.submit_transfer(db, user, data.model_dump(mode='json'))
@router.get('/api/stock-transfers')
def stock_transfers(status: str | None=None, tag: str | None=None, source_account_id: str | None=None, destination_account_id: str | None=None, sku_id: str | None=None,
                    q: str | None=None, date_from: date | None=None, date_to: date | None=None, attention: bool=False,
                    page: int=Query(1, ge=1), limit: int=Query(20, ge=1, le=100),
                    user=Depends(identity), db=database_dependency):
    return warehouse.list_transfers(db, status, dict(tag=tag,source_account_id=source_account_id,destination_account_id=destination_account_id,sku_id=sku_id,q=q,date_from=date_from,date_to=date_to,attention=attention), page=page, limit=limit)
@router.get('/api/stock-transfers/{identifier}')
def stock_transfer_detail(identifier: str, user=Depends(identity), db=database_dependency):
    return warehouse.transfer_detail(db, identifier)
@router.post('/api/stock-transfers/{identifier}/approve')
def approve_stock_transfer(identifier: str, data: StockApproval, user=Depends(identity), db=database_dependency):
    return warehouse.decide_transfer(db, user, identifier, data.model_dump(mode='json'))
@router.post('/api/stock-transfers/{identifier}/reject')
def reject_stock_transfer(identifier: str, data: StockRejection, user=Depends(identity), db=database_dependency):
    return warehouse.decide_transfer(db, user, identifier, data.model_dump(mode='json'), rejection=True)
@router.post('/api/stock-transfers/{identifier}/cancel')
def cancel_stock_transfer(identifier: str, data: StockRejection, user=Depends(identity), db=database_dependency):
    return warehouse.cancel_transfer(db, user, identifier, data.model_dump(mode='json'))

@router.post('/api/stock-transfers/{identifier}/completion')
def complete_stock_transfer(identifier: str, data: CompletionInput, user=Depends(identity), db=database_dependency):
    return warehouse.request_completion(db, user, identifier, data.model_dump(mode='json'))
@router.post('/api/stock-confirmations/{identifier}/approve')
def approve_stock_completion(identifier: str, data: StockApproval, user=Depends(identity), db=database_dependency):
    return warehouse.decide_completion(db, user, identifier, data.model_dump(mode='json'))
@router.post('/api/stock-confirmations/{identifier}/reject')
def reject_stock_completion(identifier: str, data: StockRejection, user=Depends(identity), db=database_dependency):
    return warehouse.decide_completion(db, user, identifier, data.model_dump(mode='json'), rejection=True)
@router.get('/api/inventory')
def stock_inventory(sku_id: str | None=None, account_id: str | None=None, member_id: str | None=None, custodian_id: str | None=None,
                    page: int=Query(1, ge=1), limit: int=Query(20, ge=1, le=100),
                    user=Depends(identity), db=database_dependency):
    return warehouse.inventory(db, dict(sku_id=sku_id, account_id=account_id, member_id=member_id,custodian_id=custodian_id), page=page, limit=limit)
@router.get('/api/stock-moves')
def stock_moves(sku_id: str | None=None, source_account_id: str | None=None, destination_account_id: str | None=None, transfer_id: str | None=None,
                page: int=Query(1, ge=1), limit: int=Query(20, ge=1, le=100),
                user=Depends(identity), db=database_dependency):
    return warehouse.list_moves_page(db,dict(sku_id=sku_id,source_account_id=source_account_id,destination_account_id=destination_account_id,transfer_id=transfer_id),page=page,limit=limit)

@router.post('/api/stock-transfers/{identifier}/fund-references')
def add_stock_fund_reference(identifier: str, data: StockFundReferenceInput, user=Depends(identity), db=database_dependency):
    return warehouse.add_fund_reference(db, user, identifier, data.model_dump(mode='json'))

@router.post('/api/stock-operations', status_code=201)
def submit_stock_operation(data: StockOperationInput, user=Depends(identity), db=database_dependency):
    from backend.application.stock_workflows import submit_stock_with_money
    return submit_stock_with_money(db, user, data.model_dump(mode='json'))


from backend.application import stocktakes

@router.get('/api/fund-stocktakes')
def list_fund_stocktakes(status: Literal['in_progress', 'ended'] | None=None, q: str | None=None,
                         page: int=Query(1, ge=1), limit: int=Query(20, ge=1, le=100),
                         user=Depends(identity), db=database_dependency):
    return stocktakes.list_stocktakes_page(db, 'fund', status, q, page, limit)
@router.post('/api/fund-stocktakes', status_code=201)
def create_fund_stocktake(data: StocktakeCreate, user=Depends(identity), db=database_dependency):
    return stocktakes.create_stocktake(db, user, 'fund', data.model_dump())
@router.get('/api/fund-stocktakes/{identifier}')
def get_fund_stocktake(identifier: str, user=Depends(identity), db=database_dependency):
    return stocktakes.get_stocktake(db, 'fund', identifier)
@router.patch('/api/fund-stocktakes/{identifier}')
def patch_fund_stocktake(identifier: str, data: StocktakePatch, user=Depends(identity), db=database_dependency):
    return stocktakes.update_description(db, user, 'fund', identifier, data.description)
@router.post('/api/fund-stocktakes/{identifier}/end')
def end_fund_stocktake(identifier: str, user=Depends(identity), db=database_dependency):
    return stocktakes.end_stocktake(db, user, 'fund', identifier)

@router.get('/api/stock-stocktakes')
def list_stock_stocktakes(status: Literal['in_progress', 'ended'] | None=None, q: str | None=None,
                          page: int=Query(1, ge=1), limit: int=Query(20, ge=1, le=100),
                          user=Depends(identity), db=database_dependency):
    return stocktakes.list_stocktakes_page(db, 'stock', status, q, page, limit)
@router.post('/api/stock-stocktakes', status_code=201)
def create_stock_stocktake(data: StocktakeCreate, user=Depends(identity), db=database_dependency):
    return stocktakes.create_stocktake(db, user, 'stock', data.model_dump())
@router.get('/api/stock-stocktakes/{identifier}')
def get_stock_stocktake(identifier: str, user=Depends(identity), db=database_dependency):
    return stocktakes.get_stocktake(db, 'stock', identifier)
@router.patch('/api/stock-stocktakes/{identifier}')
def patch_stock_stocktake(identifier: str, data: StocktakePatch, user=Depends(identity), db=database_dependency):
    return stocktakes.update_description(db, user, 'stock', identifier, data.description)
@router.post('/api/stock-stocktakes/{identifier}/end')
def end_stock_stocktake(identifier: str, user=Depends(identity), db=database_dependency):
    return stocktakes.end_stocktake(db, user, 'stock', identifier)


def create_app():
    mcp_app = create_mcp_app()

    @asynccontextmanager
    async def lifespan(app):
        auth_config.validate_auth_config()
        async with mcp_app.session_manager.run():
            yield

    app = FastAPI(title='FGAS 资金与库存工作台', lifespan=lifespan)
    app.add_exception_handler(DomainError, domain_error)
    app.include_router(router)
    # The SDK owns the exact /mcp path without a mount redirect.
    app.mount('/', mcp_app)
    return app


app = create_app()

"""Atomic creation of independent money and stock records."""
from copy import deepcopy
from backend.application import funds, member_claims, warehouse
from backend.infrastructure import store, stock_store
from backend.infrastructure.models import StockOperation, new_id
from backend.kernel.accounting import DomainError


def operation_view(db, operation):
    item = funds.get_transfer(db, operation.fund_transfer_id)
    result = dict(stock_transfer=warehouse.transfer_view(db, stock_store.get_transfer(db, operation.stock_transfer_id)),
                  fund_transfer=funds.transfer_view(db, item, True))
    if store.get_claim(db, item.id): result['claim'] = member_claims.get_claim(db, item.id)
    return result


def submit_stock_with_money(db, user, data: dict) -> dict:
    warehouse.authorize(db, user)
    existing = stock_store.existing_operation(db, user.id, data['idempotency_key'])
    if existing:
        if existing.payload != data: raise DomainError('幂等键已用于不同内容', 409)
        return operation_view(db, existing)
    if data['stock'].get('fund_transfer_ids'):
        raise DomainError('新建钱货操作不能同时引用已有资金流水')
    # Public caller keys share the child namespaces; allocate and check under the
    # same advisory lock before writing anything, even for accidental collisions.
    while True:
        identifier = new_id()
        money_key, stock_key = f'stock-operation:{identifier}:money', f'stock-operation:{identifier}:stock'
        if not store.existing_submission(db, user.id, money_key) and not stock_store.existing_submission(db, user.id, stock_key): break
    # Savepoints also protect direct application callers that catch a failure.
    with db.begin_nested():
        operation = stock_store.create(db, StockOperation, dict(id=identifier, actor_id=user.id,
            idempotency_key=data['idempotency_key'], payload=deepcopy(data)))
        money = deepcopy(data['money']['data']) | dict(idempotency_key=money_key)
        if data['money']['kind'] == 'member_claim':
            fund_id = member_claims.submit_claim(db, user, money)['id']
        elif data['money']['kind'] == 'fund_transfer':
            fund_id = funds.submit(db, user, money).id
        else:
            raise DomainError('资金动作类型无效')
        stock = deepcopy(data['stock']) | dict(idempotency_key=stock_key, fund_transfer_ids=[fund_id])
        stock_id = warehouse.submit_transfer(db, user, stock)['id']
        operation.stock_transfer_id, operation.fund_transfer_id = stock_id, fund_id
        store.flush(db)
        # Use this transaction's views: a separate read snapshot cannot see these
        # records until the HTTP transaction commits.
        result = dict(stock_transfer=warehouse.transfer_view(db, stock_store.get_transfer(db, stock_id)),
                      fund_transfer=funds.transfer_view(db, funds.get_transfer(db, fund_id), True))
        if data['money']['kind'] == 'member_claim': result['claim'] = member_claims.get_claim(db, fund_id)
        return result

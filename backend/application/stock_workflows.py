"""Money and stock share the HTTP transaction; their lifecycles stay independent."""
from backend.application import funds, member_claims, warehouse
from backend.kernel.accounting import DomainError


def submit_stock_with_money(db, user, data):
    warehouse.authorize(db, user)
    if data['stock'].get('fund_transfer_ids'):
        raise DomainError('新建钱货操作不能同时引用已有资金流水')
    money = data['money']['data']
    if data['money']['kind'] == 'member_claim':
        fund_id = member_claims.submit_claim(db, user, money)['id']
    elif data['money']['kind'] == 'fund_transfer':
        fund_id = funds.submit(db, user, money).id
    else:
        raise DomainError('资金动作类型无效')
    stock = warehouse.submit_transfer(db, user, data['stock'] | dict(fund_transfer_ids=[fund_id]))
    result = dict(stock_transfer=stock, fund_transfer=funds.transfer_view(db, funds.get_transfer(db, fund_id), True))
    if data['money']['kind'] == 'member_claim': result['claim'] = member_claims.get_claim(db, fund_id)
    return result

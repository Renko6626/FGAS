from backend.application import funds, warehouse
from backend.kernel.accounting import DomainError

def submit_stock_with_money(db,user,data):
    warehouse.authorize(db,user)
    if data['stock'].get('fund_transfer_ids'): raise DomainError('新建资金记录时不同时引用已有资金流水')
    money=funds.submit(db,user,data['money'])
    stock=warehouse.submit_transfer(db,user,data['stock'] | dict(fund_transfer_ids=[money.id]))
    return dict(stock_transfer=stock,fund_transfer=funds.transfer_view(db,money,True))

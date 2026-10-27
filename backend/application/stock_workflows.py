from backend.application import funds, warehouse
from backend.application.identity import authorize_write
from backend.application.agent_access import require_operator
from backend.kernel.accounting import DomainError

def submit_stock_with_money(db,user,data, *, access=None):
    authorize_write(db, user, trusted=False)
    require_operator(user, access)
    if data['stock'].get('fund_transfer_codes'): raise DomainError('新建资金记录时不同时引用已有资金流水')
    money=funds.submit(db,user,data['money'], access=access, submit_mode='direct' if access else None)
    stock=warehouse.submit_transfer(db,user,data['stock'] | dict(fund_transfer_codes=[money.code]), access=access, submit_mode='direct' if access else None)
    return dict(stock_transfer=stock,fund_transfer=funds.transfer_view(db,money,True))

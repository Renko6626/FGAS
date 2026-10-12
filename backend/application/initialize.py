import os
from sqlalchemy import select
from backend.infrastructure.database import Session
from backend.infrastructure.models import User, Account, FundAccount, Location

def initialize():
    if os.getenv('AUTH_MODE') != 'development': raise RuntimeError('Initialization requires AUTH_MODE=development')
    with Session.begin() as db:
        for identifier, name, role in [(os.getenv('INITIAL_ADMIN_ID', 'admin'), os.getenv('INITIAL_ADMIN_NAME', '管理员'), 'admin'), ('trusted', '受信任成员', 'trusted'), ('untrusted', '待审批成员', 'untrusted')]:
            if not db.get(User, identifier): db.add(User(id=identifier, display_name=name, role=role, active=True))
        for identifier, name, kind, is_fund in [('bank', '银行账户', 'asset', True), ('cash', '现金', 'asset', True), ('income', '收入', 'income', False), ('expense', '费用', 'expense', False), ('opening', '期初权益', 'equity', False)]:
            if not db.get(Account, identifier):
                db.add(Account(id=identifier, name=name, kind=kind, tags=['示例'])); db.flush()
                if is_fund: db.add(FundAccount(account_id=identifier))
        if not db.get(Location, 'main'): db.add(Location(id='main', name='主存放处', custodian_label='', tags=['示例']))
if __name__ == '__main__': initialize()

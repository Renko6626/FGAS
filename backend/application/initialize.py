import os
from backend.infrastructure.store import seed_development

def initialize():
    if os.getenv('AUTH_MODE') != 'development': raise RuntimeError('Initialization requires AUTH_MODE=development')
    seed_development(os.getenv('INITIAL_ADMIN_ID', 'admin'), os.getenv('INITIAL_ADMIN_NAME', '管理员'))
if __name__ == '__main__': initialize()

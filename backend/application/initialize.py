import argparse
import os
from backend.infrastructure import auth_config
from backend.infrastructure.store import reset_schema, seed_development, upgrade_schema

def initialize(reset=False):
    mode = auth_config.validate_auth_config()
    if mode == 'casdoor':
        if reset: raise RuntimeError('--reset is only available in development mode')
        upgrade_schema()
        return
    if reset: reset_schema()
    upgrade_schema()
    seed_development(os.getenv('INITIAL_ADMIN_ID','admin'),os.getenv('INITIAL_ADMIN_NAME','管理员'))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Initialize the FGAS database')
    parser.add_argument('--reset',action='store_true',help='Delete and rebuild FGAS development tables')
    initialize(parser.parse_args().reset)

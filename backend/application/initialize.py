import argparse
import os
from backend.infrastructure.store import create_schema, reset_schema, seed_development

def initialize(reset=False):
    if os.getenv('AUTH_MODE') != 'development': raise RuntimeError('Initialization requires AUTH_MODE=development')
    if reset: reset_schema()
    else: create_schema()
    seed_development(os.getenv('INITIAL_ADMIN_ID', 'admin'), os.getenv('INITIAL_ADMIN_NAME', '管理员'))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Initialize the FGAS development database')
    parser.add_argument('--reset', action='store_true', help='Delete and rebuild configured FGAS application tables')
    initialize(reset=parser.parse_args().reset)

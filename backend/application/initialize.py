import argparse
import os
from backend.infrastructure.store import create_schema, reset_schema, seed_development

def initialize(reset=False, initialize_stock_profiles=False):
    if os.getenv('AUTH_MODE') != 'development': raise RuntimeError('Initialization requires AUTH_MODE=development')
    if reset: reset_schema()
    else: create_schema()
    seed_development(os.getenv('INITIAL_ADMIN_ID', 'admin'), os.getenv('INITIAL_ADMIN_NAME', '管理员'))
    if initialize_stock_profiles:
        from backend.infrastructure.database import Session
        from backend.infrastructure.stock_store import initialize_profiles
        with Session.begin() as db:
            identifiers = initialize_profiles(db)
        print(f'Initialized physical stock profiles: {len(identifiers)}; location_ids={identifiers}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Initialize the FGAS development database')
    parser.add_argument('--reset', action='store_true', help='Delete and rebuild configured FGAS application tables')
    parser.add_argument('--initialize-stock-profiles', action='store_true', help='Explicitly add physical profiles for legacy locations; preserve custodian text')
    args = parser.parse_args()
    initialize(reset=args.reset, initialize_stock_profiles=args.initialize_stock_profiles)

#!/usr/bin/env python3
"""Run the opt-in local prototype on fgas_test, without loading unrelated keys."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
common = Path(subprocess.check_output(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'], text=True).strip()).parent
os.environ.setdefault('DATABASE_URL', f'postgresql+psycopg2://fgas@/fgas_test?host={common / ".runtime"}&port=55438')
os.environ['AUTH_MODE'] = 'development'
os.environ['FGAS_WEB_AGENT_PROTOTYPE'] = '1'
port = int(os.getenv('FGAS_WEB_AGENT_PORT', '10632'))
os.environ['FGAS_WEB_AGENT_MCP_URL'] = f'http://127.0.0.1:{port}/mcp'
os.environ.setdefault('PYDANTIC_AI_NO_BANNER', '1')
# Read only the FGAS-specific model key, never the authentication system's keys.
if not os.getenv('FGAS_DEEPSEEK_API_KEY'):
    from dotenv import dotenv_values
    source = ROOT / '.env' if (ROOT / '.env').exists() else common / '.env'
    if source.exists():
        key = dotenv_values(source).get('FGAS_DEEPSEEK_API_KEY')
        if key:
            os.environ['FGAS_DEEPSEEK_API_KEY'] = key

from sqlalchemy import text
from backend.infrastructure.database import engine
with engine.connect() as db:
    if db.scalar(text('SELECT current_database()')) != 'fgas_test':
        raise SystemExit('The prototype launcher requires fgas_test; it never uses the daily database')

import uvicorn
uvicorn.run('backend.entrypoints.http:app', host='127.0.0.1', port=port)

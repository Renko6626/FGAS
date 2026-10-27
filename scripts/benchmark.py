#!/usr/bin/env python3
"""Prepare the fixed, isolated FGAS benchmark through its real human HTTP API."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'benchmarks' / 'gensokyo-circle-v1'
DATABASE = 'fgas_benchmark'


def common_root():
    common = subprocess.check_output(['git', 'rev-parse', '--git-common-dir'], cwd=ROOT, text=True).strip()
    return (ROOT / common).resolve().parent


RUNTIME = common_root() / '.runtime' / 'benchmarks' / 'gensokyo-circle-v1'


def read_json(path):
    return json.loads(path.read_text())


def private_json(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def database_url():
    raw = os.environ.get('DATABASE_URL')
    url = make_url(raw) if raw else URL.create(
        'postgresql+psycopg2', username='fgas', database=DATABASE,
        query={'host': str(common_root() / '.runtime'), 'port': '55438'})
    if url.get_backend_name() != 'postgresql':
        raise RuntimeError('基准只支持既有 PostgreSQL')
    # Never let a DSN query or service override the explicitly selected database.
    if set(url.query) & {'dbname', 'database', 'service'}:
        raise RuntimeError('DATABASE_URL 不可包含 dbname/database/service 查询参数')
    return url.set(drivername='postgresql+psycopg2', database=DATABASE)


def checked_engine(url):
    if url.database != DATABASE:
        raise RuntimeError('只允许 fgas_benchmark')
    engine = create_engine(url)
    with engine.connect() as connection:
        if connection.scalar(text('SELECT current_database()')) != DATABASE:
            raise RuntimeError('实际连接不是 fgas_benchmark；停止')
    return engine


def pg_dump(url):
    executable = shutil.which('pg_dump')
    if not executable:
        candidates = sorted(Path('/usr/lib/postgresql').glob('*/bin/pg_dump'), reverse=True)
        executable = str(candidates[0]) if candidates else None
    if not executable:
        raise RuntimeError('reset 需要 pg_dump；未备份，未重建')
    backup = RUNTIME / ('backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.dump')
    params = url.translate_connect_args(username='user', database='dbname') | dict(url.query)
    # Pass the explicit DSN without a password; PGDATABASE alone does not expand a DSN.
    password = params.pop('password', None)
    from psycopg2.extensions import make_dsn
    env = os.environ.copy()
    if password is not None:
        env['PGPASSWORD'] = password
    descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            subprocess.run([executable, '--format=custom', '--dbname', make_dsn(**params)],
                           env=env, stdout=stream, check=True)
    except BaseException:
        backup.unlink(missing_ok=True)
        raise
    print(f'重建前备份：{backup}')


def prepare_database(url, reset):
    admin = create_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT')
    try:
        with admin.connect() as connection:
            if connection.scalar(text('SELECT current_database()')) != 'postgres':
                raise RuntimeError('建库连接不是 postgres；停止')
            exists = connection.scalar(text('SELECT 1 FROM pg_database WHERE datname=:name'), {'name': DATABASE})
            if exists:
                engine = checked_engine(url)
                try:
                    with engine.connect() as benchmark:
                        nonempty = benchmark.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r','p','v','m','S'))"))
                finally:
                    engine.dispose()
                if reset:
                    pg_dump(url)
                    # No FORCE or session termination: a running benchmark must be stopped by its operator.
                    connection.execute(text('DROP DATABASE fgas_benchmark'))
                    exists = False
                elif nonempty:
                    raise RuntimeError('fgas_benchmark 非空；init 不会再次灌入，请使用 reset（先备份）')
            if not exists:
                connection.execute(text('CREATE DATABASE fgas_benchmark'))
    finally:
        admin.dispose()
    engine = checked_engine(url)
    engine.dispose()
    subprocess.run([sys.executable, '-m', 'backend.application.initialize'], cwd=ROOT, env=api_env(url), check=True)


def api_env(url):
    return os.environ | {'DATABASE_URL': url.render_as_string(hide_password=False),
                         'AUTH_MODE': 'development', 'COOKIE_SECURE': 'false',
                         'INITIAL_ADMIN_ID': 'admin', 'INITIAL_ADMIN_NAME': '林舟（财务操作身份）'}


@contextmanager
def temporary_api(url):
    # The loader only talks to its own subprocess, never an arbitrary existing service.
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    with (RUNTIME / 'api.log').open('a') as log:
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.entrypoints.http:app',
                                    '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT, env=api_env(url), stdout=log, stderr=log)
        try:
            base = f'http://127.0.0.1:{port}'
            deadline = time.monotonic() + 15
            # Readiness polling only. Business requests below are never retried.
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f'基准 API 启动失败；查看 {RUNTIME / "api.log"}')
                try:
                    response = httpx.get(base + '/api/health', timeout=0.5, trust_env=False)
                    if response.status_code == 200:
                        break
                except httpx.ConnectError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError('基准 API 启动超时')
            yield base
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


class API:
    def __init__(self, base):
        self.clients = {role: httpx.Client(base_url=base, timeout=30, trust_env=False) for role in ('admin', 'trusted', 'untrusted')}
        for role in self.clients:
            self.request('POST', '/api/auth/login', {'user_id': role}, role=role)

    def close(self):
        for client in self.clients.values():
            client.close()

    def request(self, method, path, data=None, *, role='admin', params=None):
        response = self.clients[role].request(method, path, json=data, params=params)
        if response.is_error:
            raise RuntimeError(f'{method} {path}: HTTP {response.status_code}: {response.text}')
        return response.json()

    def pages(self, path, **params):
        items = []
        page = 1
        while True:
            value = self.request('GET', path, params=params | {'page': page, 'limit': 100})
            items.extend(value['items'])
            if len(items) >= value['total']:
                return items
            page += 1


def load(api):
    scenario = read_json(PACKAGE / 'scenario.json')
    mapping = {kind: {} for kind in ('members', 'accounts', 'stock_accounts', 'skus', 'funds', 'stock', 'confirmations')}
    for member in scenario['members']:
        value = api.request('POST', '/api/members', {k: member[k] for k in ('name', 'note')})
        mapping['members'][member['key']] = value['code']
    for collection, path in [('accounts', '/api/accounts'), ('stock_accounts', '/api/stock-accounts')]:
        for account in scenario[collection]:
            values = {k: account[k] for k in ('name', 'kind')}
            values['tags'] = ['基准:幻想结界']
            if account['member']:
                values['member_code'] = mapping['members'][account['member']]
            if account['seed_name']:
                values.pop('kind')
                seed = next(row for row in api.request('GET', path) if row['name'] == account['seed_name'])
                value = api.request('PATCH', path + '/' + seed['code'], values)
            else:
                value = api.request('POST', path, values)
            mapping[collection][account['key']] = value['code']
    for sku in scenario['skus']:
        # Old variants are disabled after their historical movements have been recorded.
        value = api.request('POST', '/api/skus', sku | {'active': True})
        mapping['skus'][sku['code']] = value['code']
    for event in scenario['events']:
        kind = event['type']
        if kind in ('fund', 'stock'):
            collection = 'accounts' if kind == 'fund' else 'stock_accounts'
            values = dict(source_account_code=mapping[collection][event['source']],
                          destination_account_code=mapping[collection][event['destination']],
                          effective_date=event['date'], description=event['description'], tags=event['tags'])
            state = event['state']
            if kind == 'fund':
                values['amount'] = event['amount']
                value = api.request('POST', '/api/transfers', values, role='untrusted')
                mapping['funds'][event['key']] = value['code']
                action = 'approve' if state == 'posted' else 'reject' if state == 'rejected' else None
                if action:
                    decision = {'expected_version': value['version']}
                    if action == 'reject':
                        decision['reason'] = '基准历史：重复申请'
                    api.request('POST', f'/api/transfers/{value["code"]}/{action}', decision)
            else:
                values |= dict(lines=event['lines'], source_reference=event['reference'],
                               related_transfer_code=mapping['stock'].get(event['related']),
                               fund_transfer_codes=[mapping['funds'][ref] for ref in event['funds']])
                value = api.request('POST', '/api/stock-transfers', values, role='untrusted')
                identifier = value['code']
                mapping['stock'][event['key']] = identifier
                path = '/api/stock-transfers/' + identifier
                if state == 'rejected':
                    api.request('POST', path + '/reject', {'reason': '基准历史：重复备货'})
                elif state != 'pending':
                    api.request('POST', path + '/approve', {})
                    if state == 'cancelled':
                        api.request('POST', path + '/cancel', {'reason': '基准历史：供应商无货'})
                    elif state in ('completed', 'confirmation_pending'):
                        completion = api.request('POST', path + '/completion', {'effective_date': event['date']}, role='untrusted')
                        confirmation = completion['confirmation_code']
                        mapping['confirmations'][event['key']] = confirmation
                        if state == 'completed':
                            api.request('POST', f'/api/stock-confirmations/{confirmation}/approve', {})
        elif kind == 'match':
            api.request('POST', f'/api/transfers/{mapping["funds"][event["payment"]]}/settlement-matches',
                        {'allocations': [{'item_transfer_code': mapping['funds'][event['item']], 'amount': event['amount']}]})
        elif kind == 'custody':
            api.request('PATCH', '/api/stock-accounts/' + mapping['stock_accounts'][event['account']],
                        {'member_code': mapping['members'][event['member']]})
        else:
            raise RuntimeError('未知事件：' + kind)
    for sku in scenario['skus']:
        if not sku['active']:
            api.request('PATCH', '/api/skus/' + sku['code'], {'active': False})
    credentials = {}
    for name, role, level in [('ordinary-low', 'untrusted', 'low'), ('trusted-low', 'trusted', 'low'),
                              ('admin-low', 'admin', 'low'), ('admin-high', 'admin', 'high')]:
        credentials[name] = api.request('POST', '/api/agent-credentials',
                                        {'name': f'基准 {name}', 'level': level}, role=role)
    private_json(RUNTIME / 'mapping.json', mapping)
    private_json(RUNTIME / 'credentials.json', credentials)
    return mapping


def check(api, mapping):
    expected = read_json(PACKAGE / 'golden.json')['baseline']
    def equal(actual, wanted, label):
        if actual != wanted:
            raise RuntimeError(f'核对失败 {label}: {actual!r} != {wanted!r}')
    skus = api.request('GET', '/api/skus')
    # The current human directory is a complete list; Agent tools may paginate it.
    equal(len(skus), 32, 'SKU数量')
    equal(sum(s['active'] for s in skus), 28, '启用数量')
    for category, count in [('徽章', 16), ('立牌', 8), ('同人本', 8)]:
        equal(sum('类别:' + category in s['tags'] for s in skus), count, category)
    equal(sorted(s['code'] for s in skus if not s['active']), expected['inactive_codes'], '停用旧款')
    accounts = api.request('GET', '/api/accounts')
    equal(sum(a['kind'] == 'public' for a in accounts), 1, '唯一公账')
    for symbol, amount in expected['balances_minor'].items():
        equal(next(a['balance_minor'] for a in accounts if a['code'] == mapping['accounts'][symbol]), amount, symbol + '余额')
    rows = api.pages('/api/inventory', sku_code='BAD-01-A')
    actual = {r['account_code']: int(r['quantity']) for r in rows if int(r['quantity'])}
    wanted = {mapping['stock_accounts'][key]: quantity for key, quantity in expected['bad_01_a_locations'].items()}
    equal(actual, wanted, 'BAD-01-A位置')
    equal(sum(actual.values()), 297, 'BAD-01-A组织库存')
    totals = api.request('GET', '/api/inventory', params={'sku_code': 'BAD-01-A'})['totals'][0]
    equal(tuple(int(totals[key]) for key in ('quantity', 'incoming_to_org_quantity', 'internal_transfer_quantity', 'outgoing_from_org_quantity')),
          (297, 120, 10, 0), 'BAD-01-A正式与三类计划')
    equal(sum(int(totals[key]) for key in ('incoming_to_org_quantity', 'internal_transfer_quantity', 'outgoing_from_org_quantity')), 130, '计划明细只计一次')
    for symbol, status in expected['stock_states'].items():
        value = api.request('GET', '/api/stock-transfers/' + mapping['stock'][symbol])
        equal(value['status'], status, symbol + '状态')
        if symbol in ('unarrived', 'outbound'):
            equal([(line['sku_code'], int(line['quantity'])) for line in value['lines']],
                  [('BAD-01-A', 120 if symbol == 'unarrived' else 10)], symbol + '在途')
        if symbol == 'confirmation_pending':
            equal([c['status'] for c in value['confirmations']], ['pending'], '完成申请待审')
    unarrived = api.request('GET', '/api/transfers/' + mapping['funds']['unarrived_payment'])
    equal((unarrived['status'], unarrived['amount_minor']), ('posted', 96000), '在途已付款')
    detail = api.request('GET', '/api/stock-accounts/' + mapping['stock_accounts']['main'])
    equal(detail['member_code'], mapping['members']['xu'], '当前负责人许棠')
    history = detail['responsibility_history']
    equal(len(history), 2, '两段负责人历史')
    equal({h['member_code'] for h in history}, {mapping['members']['tang'], mapping['members']['xu']}, '负责人唐悦交接许棠')
    equal(sum(h['valid_to'] is None for h in history), 1, '唯一当前负责人')
    outstanding = api.pages('/api/settlement-outstanding')
    normalized = sorted((r['account_name'], r['kind'], r['direction'], r['remaining_minor']) for r in outstanding)
    equal(normalized, sorted(tuple(row) for row in expected['outstanding']), '未结原收支及付款')
    ye = api.request('GET', '/api/accounts/' + mapping['accounts']['ye'] + '/settlement-overview')
    equal(next(r['outstanding_minor'] for r in ye['expenses'] if r['transfer']['code'] == mapping['funds']['ye_wrong']), 0, '叶青错单已匹配')
    equal(next(r['matched_minor'] for r in ye['settlements'] if r['transfer']['code'] == mapping['funds']['ye_refund']), 30000, '叶青原付款已匹配300')
    credentials = api.request('GET', '/api/agent-credentials')
    equal(sorted((c['owner_user_id'], c['level']) for c in credentials if c['active']),
          [('admin', 'high'), ('admin', 'low'), ('trusted', 'low'), ('untrusted', 'low')], '四种连接身份')
    equal(len(api.pages('/api/transfers')), expected['fund_transfer_count'], '资金单数量')
    equal(len(api.pages('/api/stock-transfers')), expected['stock_transfer_count'], '货物单数量')
    print('核对通过：32SKU，唯一公账16100元，BAD-01-A正式297（227/50/20），外部流入计划120/内部调拨10/对外0，结算及负责人历史，四种连接')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('init', 'reset', 'serve', 'check'))
    parser.add_argument('--port', type=int, default=10623, help='serve 的独立回环端口（默认10623）')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port 必须为1至65535')
    RUNTIME.mkdir(parents=True, exist_ok=True, mode=0o700)
    url = database_url()
    if args.command in ('init', 'reset'):
        prepare_database(url, args.command == 'reset')
    else:
        engine = checked_engine(url)
        engine.dispose()
    if args.command == 'serve':
        print(f'独立基准 API/MCP：http://127.0.0.1:{args.port} / http://127.0.0.1:{args.port}/mcp', flush=True)
        os.chdir(ROOT)
        os.execvpe(sys.executable, [sys.executable, '-m', 'uvicorn', 'backend.entrypoints.http:app',
                                   '--host', '127.0.0.1', '--port', str(args.port)], api_env(url))
    with temporary_api(url) as base:
        api = API(base)
        try:
            mapping = load(api) if args.command in ('init', 'reset') else read_json(RUNTIME / 'mapping.json')
            check(api, mapping)
        finally:
            api.close()
    print(f'本轮私有映射和凭据：{RUNTIME}；仅向受测Agent提供当前任务的一枚密钥')


if __name__ == '__main__':
    try:
        main()
    except SQLAlchemyError as error:
        print(f'基准停止：数据库操作失败（{type(error).__name__}）；核对本机连接及基准服务占用，不会重试或终止其他连接', file=sys.stderr)
        sys.exit(1)
    except (RuntimeError, subprocess.CalledProcessError, OSError, httpx.HTTPError) as error:
        print(f'基准停止：{error}', file=sys.stderr)
        sys.exit(1)

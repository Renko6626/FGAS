"""Private image attachments through the real HTTP path; isolated PostgreSQL fixture only."""
from backend.tests.conftest import seed_code

PNG = b'\x89PNG\r\n\x1a\n' + b'image-body-bytes'
JPEG = b'\xff\xd8\xff' + b'jpeg-body'
TEXT = b'this is not an image'


def transfer(client):
    return client.post('/api/transfers', json=dict(
        source_account_code=seed_code('opening'), destination_account_code=seed_code('fund_pool'),
        amount='100', effective_date='2026-11-04')).json()


def upload(client, target_kind, target_code, data=PNG, name='receipt.png', **form):
    return client.post('/api/attachments', data=dict(target_kind=target_kind, target_code=target_code, **form),
                       files={'file': (name, data, 'image/png')})


def test_upload_list_and_read(client, tmp_path, monkeypatch):
    monkeypatch.setenv('FGAS_ATTACHMENT_DIR', str(tmp_path))
    code = transfer(client)['code']
    response = upload(client, 'transfer', code, caption='付款截图')
    assert response.status_code == 201
    item = response.json()
    assert item['target_code'] == code and item['caption'] == '付款截图'
    assert item['content_type'] == 'image/png' and item['byte_size'] == len(PNG)
    assert item['file_url'] == f"/api/attachments/{item['id']}/file"

    listed = client.get('/api/attachments', params={'target_kind': 'transfer', 'target_code': code}).json()
    assert [entry['id'] for entry in listed] == [item['id']]

    file = client.get(item['file_url'])
    assert file.status_code == 200 and file.content == PNG
    assert file.headers['content-type'] == 'image/png'
    assert file.headers['cache-control'] == 'private, max-age=3600'
    assert [path.name for path in tmp_path.iterdir()] == [f"{item['id']}.png"]

    detail = client.get(f'/api/transfers/{code}').json()
    assert any(event['action'] == 'attachment_added' for event in detail['audit'])


def test_stock_transfer_attachment_audit(client, tmp_path, monkeypatch):
    monkeypatch.setenv('FGAS_ATTACHMENT_DIR', str(tmp_path))
    source = client.post('/api/stock-accounts', json=dict(name='商家', kind='external')).json()['code']
    target = client.post('/api/stock-accounts', json=dict(name='仓库', kind='internal')).json()['code']
    sku = client.post('/api/skus', json=dict(code='IMG-01', name='测试书', unit='本')).json()['code']
    code = client.post('/api/stock-transfers', json=dict(
        source_account_code=source, destination_account_code=target, effective_date='2026-11-04',
        lines=[dict(sku_code=sku, quantity='1')])).json()['code']
    assert upload(client, 'stock_transfer', code, data=JPEG, name='goods.jpg').status_code == 201
    detail = client.get(f'/api/stock-transfers/{code}').json()
    assert any(event['action'] == 'attachment_added' and event['detail']['attachment_id'] for event in detail['audit'])


def test_delete_permissions(client, tmp_path, monkeypatch):
    monkeypatch.setenv('FGAS_ATTACHMENT_DIR', str(tmp_path))
    code = transfer(client)['code']
    own = upload(client, 'transfer', code).json()
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    assert client.delete(f"/api/attachments/{own['id']}").status_code == 403
    client.post('/api/auth/login', json={'user_id': 'trusted'})
    assert client.delete(f"/api/attachments/{own['id']}").status_code == 200
    assert not list(tmp_path.iterdir())

    other = upload(client, 'transfer', code).json()
    client.post('/api/auth/login', json={'user_id': 'admin'})
    assert client.delete(f"/api/attachments/{other['id']}").status_code == 200
    assert client.get(other['file_url']).status_code == 404


def test_rejects_invalid_uploads(client, tmp_path, monkeypatch):
    monkeypatch.setenv('FGAS_ATTACHMENT_DIR', str(tmp_path))
    code = transfer(client)['code']
    assert upload(client, 'transfer', code, data=TEXT, name='fake.png').status_code == 400
    assert upload(client, 'transfer', 'FT-999999').status_code == 404
    assert upload(client, 'unknown', code).status_code == 400
    monkeypatch.setenv('FGAS_ATTACHMENT_MAX_BYTES', '8')
    oversized = client.post('/api/attachments', data=dict(target_kind='transfer', target_code=code),
                            files={'file': ('big.png', PNG, 'image/png')})
    assert oversized.status_code == 413


def test_sku_attachment_sets_avatar(client, tmp_path, monkeypatch):
    monkeypatch.setenv('FGAS_ATTACHMENT_DIR', str(tmp_path))
    sku = client.post('/api/skus', json=dict(code='AVATAR-01', name='测试立牌', unit='个')).json()['code']
    item = upload(client, 'sku', sku, caption='示意图').json()
    patched = client.patch(f'/api/skus/{sku}', json={'avatar_url': item['file_url']})
    assert patched.status_code == 200 and patched.json()['avatar_url'] == item['file_url']
    found = next(entry for entry in client.get('/api/skus').json() if entry['code'] == sku)
    assert found['avatar_url'] == item['file_url']
    assert client.get(item['file_url']).content == PNG


def test_admin_attachment_overview(client, tmp_path, monkeypatch):
    monkeypatch.setenv('FGAS_ATTACHMENT_DIR', str(tmp_path))
    code = transfer(client)['code']
    item = upload(client, 'transfer', code, caption='管理总览').json()
    client.post('/api/auth/login', json={'user_id': 'untrusted'})
    assert client.get('/api/admin/attachments').status_code == 403
    client.post('/api/auth/login', json={'user_id': 'admin'})
    library = client.get('/api/admin/attachments').json()
    assert library['total'] >= 1 and library['total_bytes'] >= len(PNG)
    assert any(entry['id'] == item['id'] and entry['target_code'] == code for entry in library['items'])
    filtered = client.get('/api/admin/attachments', params={'q': code}).json()
    assert filtered['total'] == 1
    assert client.get('/api/admin/attachments', params={'kind': 'sku'}).json()['total'] == 0

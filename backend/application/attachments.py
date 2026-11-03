"""Private image attachments for transfers, SKUs and accounts."""
from backend.application.directory_views import by_code
from backend.application.identity import authorize_write
from backend.infrastructure import attachment_store as files, stock_store, store
from backend.infrastructure.models import FundAccount, Sku, StockAccount, StockTransfer, StockAudit, Transfer
from backend.kernel.accounting import DomainError

TARGET_MODELS = {
    'transfer': Transfer,
    'stock_transfer': StockTransfer,
    'sku': Sku,
    'fund_account': FundAccount,
    'stock_account': StockAccount,
}
MAX_PER_TARGET = 20
MAX_CAPTION = 200
MAX_DIMENSION = 20000


def resolve_target(db, target_kind, target_code):
    model = TARGET_MODELS.get(target_kind)
    if model is None:
        raise DomainError('不支持的附件对象类型', 400)
    return by_code(db, model, (target_code or '').strip())


def view(db, item):
    uploader = store.get_user(db, item.uploaded_by)
    target = db.get(TARGET_MODELS[item.target_kind], item.target_id)
    return dict(
        id=item.id, target_kind=item.target_kind, target_code=target.code if target else None,
        caption=item.caption, content_type=item.content_type, byte_size=item.byte_size,
        width=item.width, height=item.height, original_filename=item.original_filename,
        uploaded_by_id=item.uploaded_by,
        uploaded_by_name=uploader.display_name if uploader else None,
        created_at=item.created_at,
        file_url=f'/api/attachments/{item.id}/file',
    )


def _audit(db, item, user, action):
    detail = f'图片附件 {item.id}' + (f' {item.original_filename}' if item.original_filename else '')
    if item.target_kind == 'transfer':
        store.audit(db, item.target_id, user.id, action, detail)
    elif item.target_kind == 'stock_transfer':
        stock_store.create(db, StockAudit, dict(stock_transfer_id=item.target_id, actor_id=user.id,
                                                action=action, detail={'attachment_id': item.id, 'filename': item.original_filename}))


def upload(db, user, *, target_kind, target_code, data, original_filename='', caption='', width=None, height=None):
    authorize_write(db, user, trusted=False)
    target = resolve_target(db, target_kind, target_code)
    if not data:
        raise DomainError('图片内容为空', 400)
    ext = files.image_ext(data)
    if ext is None:
        raise DomainError('只支持 PNG、JPEG 或 WebP 图片', 400)
    if len(data) > files.max_bytes():
        raise DomainError('图片超过大小限制', 413)
    for value in (width, height):
        if value is not None and not 0 < value <= MAX_DIMENSION:
            raise DomainError('图片尺寸无效', 400)
    caption = (caption or '').strip()
    if len(caption) > MAX_CAPTION:
        raise DomainError('图片说明最多 200 字', 400)
    if files.count_by_target(db, target_kind, target.id) >= MAX_PER_TARGET:
        raise DomainError(f'每个对象最多 {MAX_PER_TARGET} 张图片', 409)
    item = files.create(db, dict(
        target_kind=target_kind, target_id=target.id, uploaded_by=user.id, caption=caption,
        original_filename=(original_filename or '').strip()[:200], content_type=files.CONTENT_TYPES[ext],
        byte_size=len(data), width=width, height=height,
    ))
    try:
        files.write(item.id, data, ext)
    except OSError as exc:
        raise DomainError('图片保存失败', 500) from exc
    _audit(db, item, user, 'attachment_added')
    return view(db, item)


def list_for_target(db, target_kind, target_code):
    target = resolve_target(db, target_kind, target_code)
    return [view(db, item) for item in files.list_by_target(db, target_kind, target.id)]


def get_file(db, identifier):
    item = files.get(db, identifier)
    if item is None:
        raise DomainError('附件不存在', 404)
    path = files.file_path(item.id, item.content_type)
    if path is None or not path.is_file():
        raise DomainError('附件文件不存在', 404)
    return item, path


def remove(db, user, identifier):
    store.lock(db)
    store.refresh(db, user)
    item = files.get(db, identifier)
    if item is None:
        raise DomainError('附件不存在', 404)
    if item.uploaded_by != user.id and user.role != 'admin':
        raise DomainError('只能删除自己上传的图片', 403)
    _audit(db, item, user, 'attachment_deleted')
    files.delete(db, item)
    db.flush()
    files.remove(item.id)
    return {'ok': True}

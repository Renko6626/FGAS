"""Private attachment files: one flat directory, format sniffed from the bytes."""
import os
import tempfile
from pathlib import Path
from sqlalchemy import func, select
from backend.infrastructure.models import Attachment

DEFAULT_MAX_BYTES = 10 * 1024 * 1024
CONTENT_TYPES = {'png': 'image/png', 'jpg': 'image/jpeg', 'webp': 'image/webp'}


def attachment_dir() -> Path:
    raw = os.getenv('FGAS_ATTACHMENT_DIR', '').strip()
    if raw:
        return Path(raw).expanduser()
    return Path(__file__).resolve().parents[2] / '.runtime' / 'attachments'


def max_bytes() -> int:
    raw = os.getenv('FGAS_ATTACHMENT_MAX_BYTES', '').strip()
    if not raw:
        return DEFAULT_MAX_BYTES
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value <= 0:
        raise RuntimeError('FGAS_ATTACHMENT_MAX_BYTES must be a positive integer')
    return value


def image_ext(data: bytes) -> str | None:
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if data.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'webp'
    return None


def ext_for_content_type(content_type: str) -> str | None:
    return {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp'}.get(content_type)


def _path(identifier: str, ext: str) -> Path:
    root = attachment_dir().resolve()
    path = (root / f'{identifier}.{ext}').resolve()
    if root not in path.parents:
        raise RuntimeError('Attachment path escapes the storage directory')
    return path


def write(identifier: str, data: bytes, ext: str) -> str:
    path = _path(identifier, ext)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(data)
        os.replace(temp, path)
    except Exception:
        Path(temp).unlink(missing_ok=True)
        raise
    return str(path)


def remove(identifier: str) -> None:
    for ext in CONTENT_TYPES:
        _path(identifier, ext).unlink(missing_ok=True)


def file_path(identifier: str, content_type: str) -> Path | None:
    ext = ext_for_content_type(content_type)
    return _path(identifier, ext) if ext else None


def create(db, values):
    item = Attachment(**values)
    db.add(item)
    db.flush()
    return item


def get(db, identifier):
    return db.get(Attachment, identifier)


def list_by_target(db, target_kind, target_id):
    query = (select(Attachment)
             .where(Attachment.target_kind == target_kind, Attachment.target_id == target_id)
             .order_by(Attachment.created_at, Attachment.id))
    return list(db.scalars(query))


def count_by_target(db, target_kind, target_id):
    return int(db.scalar(select(func.count()).select_from(Attachment)
                         .where(Attachment.target_kind == target_kind, Attachment.target_id == target_id)))


def delete(db, item):
    db.delete(item)

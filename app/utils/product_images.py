# product_images.py
# Product image upload for Spare Parts and Models (Task 49).
#
# Files go to the public Supabase Storage bucket 'product-images' using the
# logged-in staff session (no service-role key). Each upload gets a random
# path, so the original file name is never used and a replaced image never
# hits a stale cache. Only URLs of this project's public bucket form are ever
# rendered as images, and only paths this module generates are ever removed.

import re
import uuid

from app.supabase_client import supabase, SUPABASE_URL

BUCKET = 'product-images'
MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_IMAGE_LABEL = '2 MB'

INVALID_IMAGE_MSG = 'Please upload a JPG, PNG or WebP image.'
EMPTY_IMAGE_MSG = 'The image file is empty.'
LARGE_IMAGE_MSG = f'The image must be {MAX_IMAGE_LABEL} or smaller.'
UPLOAD_FAILED_MSG = 'The image could not be uploaded. Please try again.'
SAVED_WITHOUT_IMAGE_MSG = 'Saved, but the image could not be uploaded. Edit the record to try again.'
REQUEST_TOO_LARGE_MSG = (
    f'The file was too large to upload. Images must be {MAX_IMAGE_LABEL} or smaller.'
)

# Extension -> image kind, declared MIME type -> image kind
_EXTENSIONS = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png', 'webp': 'webp'}
_MIME_TYPES = {'image/jpeg': 'jpeg', 'image/jpg': 'jpeg', 'image/pjpeg': 'jpeg',
               'image/png': 'png', 'image/webp': 'webp'}
# Image kind -> (stored extension, content type)
_STORED = {'jpeg': ('jpg', 'image/jpeg'), 'png': ('png', 'image/png'), 'webp': ('webp', 'image/webp')}

FOLDERS = ('parts', 'models')
_OWN_PATH = re.compile(
    r'^(?:parts|models)/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(?:jpg|png|webp)$'
)
_SAFE_PATH = re.compile(r'^[A-Za-z0-9_-][A-Za-z0-9._/-]{0,250}$')


def _public_prefix():
    return f"{(SUPABASE_URL or '').rstrip('/')}/storage/v1/object/public/{BUCKET}/"


def public_url(path):
    """Public URL of an object in the product-images bucket."""
    return _public_prefix() + path


def _bucket_path(url):
    """The object path when url has this project's public product-images form, else None."""
    if not isinstance(url, str) or not SUPABASE_URL:
        return None
    prefix = _public_prefix()
    if not url.startswith(prefix):
        return None
    path = url[len(prefix):]
    if not _SAFE_PATH.match(path) or '..' in path or '//' in path:
        return None
    return path


def display_url(url):
    """url when it is one of this project's product-images URLs (safe to render), else ''."""
    return url if _bucket_path(url) else ''


def owned_path(url):
    """
    The object path when url points to an image this module uploaded
    (parts/<uuid>.<ext> or models/<uuid>.<ext>), else None. Only these
    paths are ever passed to a Storage remove call.
    """
    path = _bucket_path(url)
    return path if path and _OWN_PATH.match(path) else None


def _sniff(data):
    """Image kind from the file's first bytes (magic numbers), or None."""
    if data[:3] == b'\xff\xd8\xff':
        return 'jpeg'
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    if len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'webp'
    return None


def read_image_upload(file_storage):
    """
    Validate an uploaded image (werkzeug FileStorage or None).

    Returns (image, error): image is None when no file was chosen, otherwise a
    dict with 'data', 'ext' and 'content_type'. The original file name is only
    used to read its extension; it is never stored or rendered.
    """
    if file_storage is None or not file_storage.filename:
        return None, None

    data = file_storage.stream.read(MAX_IMAGE_BYTES + 1)
    if not data:
        return None, EMPTY_IMAGE_MSG
    if len(data) > MAX_IMAGE_BYTES:
        return None, LARGE_IMAGE_MSG

    name = file_storage.filename
    ext_kind = _EXTENSIONS.get(name.rsplit('.', 1)[-1].lower()) if '.' in name else None
    mime_kind = _MIME_TYPES.get((file_storage.mimetype or '').lower())
    content_kind = _sniff(data)
    if not ext_kind or ext_kind != mime_kind or ext_kind != content_kind:
        return None, INVALID_IMAGE_MSG

    ext, content_type = _STORED[content_kind]
    return {'data': data, 'ext': ext, 'content_type': content_type}, None


def upload_image(folder, image):
    """
    Upload a validated image to <folder>/<uuid>.<ext> with the staff session.
    Returns the public URL. Storage errors are raised to the caller.
    """
    if folder not in FOLDERS:
        raise ValueError('Unknown image folder.')
    path = f'{folder}/{uuid.uuid4()}.{image["ext"]}'
    supabase.storage.from_(BUCKET).upload(
        path,
        image['data'],
        {'content-type': image['content_type'], 'cache-control': '31536000', 'upsert': 'false'},
    )
    return public_url(path)


def remove_image(url):
    """
    Best-effort removal of an image this module uploaded. Any other value
    (empty, external or hand-pasted URL) is left alone. Never raises.
    """
    path = owned_path(url)
    if not path:
        return False
    try:
        supabase.storage.from_(BUCKET).remove([path])
        return True
    except Exception:
        return False

"""
Абстракция над хранилищем файлов.
Если заданы SUPABASE_URL/SUPABASE_KEY — использует Supabase Storage.
Иначе — сохраняет локально в static/uploads.
"""
import os
import uuid
from flask import current_app, url_for

ALLOWED_EXT = {
    'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt',
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'heic',
}


def _ext(filename: str) -> str:
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def _supabase_client():
    url = current_app.config.get('SUPABASE_URL')
    key = current_app.config.get('SUPABASE_KEY')
    if not url or not key:
        return None
    try:
        from supabase import create_client
    except ImportError:
        return None
    return create_client(url, key)


def save_file(file) -> str:
    """Сохраняет файл, возвращает публичный URL."""
    if not file or not file.filename:
        return None

    ext = _ext(file.filename)
    if ext not in ALLOWED_EXT:
        raise ValueError(f'Недопустимый формат файла: .{ext}')

    name = f'{uuid.uuid4().hex}.{ext}'
    data = file.read()
    bucket = current_app.config.get('SUPABASE_BUCKET', 'uploads')

    client = _supabase_client()
    if client is not None:
        mime = file.mimetype or 'application/octet-stream'
        client.storage.from_(bucket).upload(
            name, data, {'content-type': mime, 'upsert': 'true'}
        )
        return client.storage.from_(bucket).get_public_url(name)

    # fallback: локально
    folder = os.path.join(current_app.root_path, 'static', 'uploads')
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), 'wb') as f:
        f.write(data)
    return url_for('static', filename=f'uploads/{name}')

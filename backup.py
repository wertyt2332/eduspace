"""
Модуль бэкапа БД: экспорт/импорт в JSON, синхронизация с Supabase Storage.
"""
import json
import os
from datetime import datetime

from flask import current_app
from extensions import db
from models import User, Section, Subsection, Task, Submission, Material


BACKUP_FILENAME = 'backup.json'


def _iso(dt):
    return dt.isoformat() if dt else None


def _dt(s):
    return datetime.fromisoformat(s) if s else None


# ---------- Экспорт ----------

def dump_to_dict():
    """Собирает всю БД в словарь."""
    return {
        'version': 2,
        'exported_at': datetime.utcnow().isoformat(),
        'users': [
            {
                'id': u.id,
                'login': u.login,
                'password_hash': u.password_hash,
                'full_name': u.full_name,
                'role': u.role,
                'created_at': _iso(u.created_at),
            }
            for u in User.query.all()
        ],
        'sections': [
            {
                'id': s.id,
                'title': s.title,
                'description': s.description or '',
                'is_visible': s.is_visible,
                'created_at': _iso(s.created_at),
                'teacher_ids': [t.id for t in s.teachers],
                'student_ids': [st.id for st in s.students],
            }
            for s in Section.query.all()
        ],
        'subsections': [
            {
                'id': sub.id,
                'section_id': sub.section_id,
                'title': sub.title,
                'description': sub.description or '',
                'order': sub.order,
                'is_visible': sub.is_visible,
                'created_at': _iso(sub.created_at),
            }
            for sub in Subsection.query.all()
        ],
        'tasks': [
            {
                'id': t.id,
                'subsection_id': t.subsection_id,
                'title': t.title,
                'description': t.description or '',
                'task_type': t.task_type,
                'max_score': t.max_score,
                'deadline': _iso(t.deadline),
                'is_visible': t.is_visible,
                'order': t.order,
                'options_json': t.options_json or '[]',
                'created_at': _iso(t.created_at),
            }
            for t in Task.query.all()
        ],
        'materials': [
            {
                'id': m.id,
                'subsection_id': m.subsection_id,
                'title': m.title,
                'material_type': m.material_type,
                'content': m.content or '',
                'file_url': m.file_url,
                'order': m.order,
                'is_visible': m.is_visible,
                'created_at': _iso(m.created_at),
            }
            for m in Material.query.all()
        ],
        'submissions': [
            {
                'id': s.id,
                'task_id': s.task_id,
                'student_id': s.student_id,
                'content': s.content or '',
                'file_url': s.file_url,
                'submitted_at': _iso(s.submitted_at),
                'updated_at': _iso(s.updated_at),
                'score': s.score,
                'comment': s.comment or '',
                'graded_at': _iso(s.graded_at),
                'graded_by_id': s.graded_by_id,
            }
            for s in Submission.query.all()
        ],
    }


# ---------- Импорт ----------

def _clear_all():
    """Удаляет все данные в правильном порядке (FK)."""
    Submission.query.delete()
    Task.query.delete()
    Material.query.delete()
    Subsection.query.delete()
    db.session.execute(db.text('DELETE FROM section_teachers'))
    db.session.execute(db.text('DELETE FROM section_students'))
    Section.query.delete()
    User.query.delete()
    db.session.flush()


def restore_from_dict(data, clear_first=False):
    """Восстанавливает БД из словаря. Возвращает статистику."""
    if clear_first:
        _clear_all()

    stats = {'users': 0, 'sections': 0, 'subsections': 0,
             'tasks': 0, 'materials': 0, 'submissions': 0}

    # 1) Users
    existing = {u.id for u in User.query.all()}
    for u in data.get('users', []):
        if u['id'] in existing:
            continue
        db.session.add(User(
            id=u['id'], login=u['login'],
            password_hash=u['password_hash'],
            full_name=u['full_name'], role=u['role'],
            created_at=_dt(u.get('created_at')),
        ))
        stats['users'] += 1
    db.session.flush()

    # 2) Sections
    existing = {s.id for s in Section.query.all()}
    for s in data.get('sections', []):
        if s['id'] in existing:
            continue
        db.session.add(Section(
            id=s['id'], title=s['title'],
            description=s.get('description', ''),
            is_visible=s.get('is_visible', True),
            created_at=_dt(s.get('created_at')),
        ))
        stats['sections'] += 1
    db.session.flush()

    # 3) Many-to-many links
    for s in data.get('sections', []):
        section = db.session.get(Section, s['id'])
        if not section:
            continue
        for tid in s.get('teacher_ids', []):
            u = db.session.get(User, tid)
            if u and u not in section.teachers:
                section.teachers.append(u)
        for sid in s.get('student_ids', []):
            u = db.session.get(User, sid)
            if u and u not in section.students:
                section.students.append(u)
    db.session.flush()

    # 4) Subsections
    existing = {x.id for x in Subsection.query.all()}
    for sub in data.get('subsections', []):
        if sub['id'] in existing:
            continue
        db.session.add(Subsection(
            id=sub['id'], section_id=sub['section_id'],
            title=sub['title'], description=sub.get('description', ''),
            order=sub.get('order', 0),
            is_visible=sub.get('is_visible', True),
            created_at=_dt(sub.get('created_at')),
        ))
        stats['subsections'] += 1
    db.session.flush()

    # 5) Tasks
    existing = {t.id for t in Task.query.all()}
    for t in data.get('tasks', []):
        if t['id'] in existing:
            continue
        db.session.add(Task(
            id=t['id'], subsection_id=t['subsection_id'],
            title=t['title'], description=t.get('description', ''),
            task_type=t['task_type'], max_score=t.get('max_score', 5),
            deadline=_dt(t.get('deadline')),
            is_visible=t.get('is_visible', True),
            order=t.get('order', 0),
            options_json=t.get('options_json', '[]'),
            created_at=_dt(t.get('created_at')),
        ))
        stats['tasks'] += 1
    db.session.flush()

    # 6) Materials
    existing = {m.id for m in Material.query.all()}
    for m in data.get('materials', []):
        if m['id'] in existing:
            continue
        db.session.add(Material(
            id=m['id'], subsection_id=m['subsection_id'],
            title=m['title'], material_type=m['material_type'],
            content=m.get('content', ''), file_url=m.get('file_url'),
            order=m.get('order', 0),
            is_visible=m.get('is_visible', True),
            created_at=_dt(m.get('created_at')),
        ))
        stats['materials'] += 1
    db.session.flush()

    # 7) Submissions
    existing = {s.id for s in Submission.query.all()}
    for s in data.get('submissions', []):
        if s['id'] in existing:
            continue
        db.session.add(Submission(
            id=s['id'], task_id=s['task_id'], student_id=s['student_id'],
            content=s.get('content', ''), file_url=s.get('file_url'),
            submitted_at=_dt(s.get('submitted_at')),
            updated_at=_dt(s.get('updated_at')),
            score=s.get('score'), comment=s.get('comment', ''),
            graded_at=_dt(s.get('graded_at')),
            graded_by_id=s.get('graded_by_id'),
        ))
        stats['submissions'] += 1

    db.session.commit()
    return stats


# ---------- Supabase ----------

def save_to_supabase():
    """Загружает backup.json в Supabase Storage. Возвращает (ok, error)."""
    from storage import _supabase_client
    client = _supabase_client()
    if client is None:
        return False, 'Supabase не настроен'

    bucket = current_app.config.get('SUPABASE_BUCKET', 'uploads')
    data = dump_to_dict()
    payload = json.dumps(data, ensure_ascii=False).encode('utf-8')

    try:
        client.storage.from_(bucket).upload(
            BACKUP_FILENAME, payload,
            {'content-type': 'application/json', 'upsert': 'true'}
        )
        return True, None
    except Exception as e:
        return False, str(e)


def load_from_supabase():
    """Скачивает backup.json из Supabase. Возвращает (data, error)."""
    from storage import _supabase_client
    client = _supabase_client()
    if client is None:
        return None, 'Supabase не настроен'

    bucket = current_app.config.get('SUPABASE_BUCKET', 'uploads')
    try:
        raw = client.storage.from_(bucket).download(BACKUP_FILENAME)
        return json.loads(raw.decode('utf-8')), None
    except Exception as e:
        return None, str(e)


# ---------- Локальный файл ----------

def save_to_local_file(path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(dump_to_dict(), f, ensure_ascii=False, indent=2)


def load_from_local_file(path):
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

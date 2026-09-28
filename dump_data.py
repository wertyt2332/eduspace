"""
Выгружает всю базу данных в seed_data.json.
Запуск: python dump_data.py
"""
import json
from datetime import datetime

from app import app
from extensions import db
from models import User, Section, Subsection, Task, Submission, Material


def iso(dt):
    return dt.isoformat() if dt else None


def dump():
    with app.app_context():
        data = {
            'users': [
                {
                    'id': u.id,
                    'login': u.login,
                    'password_hash': u.password_hash,
                    'full_name': u.full_name,
                    'role': u.role,
                    'created_at': iso(u.created_at),
                }
                for u in User.query.all()
            ],
            'sections': [
                {
                    'id': s.id,
                    'title': s.title,
                    'description': s.description,
                    'is_visible': s.is_visible,
                    'created_at': iso(s.created_at),
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
                    'description': sub.description,
                    'order': sub.order,
                    'is_visible': sub.is_visible,
                    'created_at': iso(sub.created_at),
                }
                for sub in Subsection.query.all()
            ],
            'tasks': [
                {
                    'id': t.id,
                    'subsection_id': t.subsection_id,
                    'title': t.title,
                    'description': t.description,
                    'task_type': t.task_type,
                    'max_score': t.max_score,
                    'deadline': iso(t.deadline),
                    'is_visible': t.is_visible,
                    'order': t.order,
                    'options_json': t.options_json,
                    'created_at': iso(t.created_at),
                }
                for t in Task.query.all()
            ],
            'materials': [
                {
                    'id': m.id,
                    'subsection_id': m.subsection_id,
                    'title': m.title,
                    'material_type': m.material_type,
                    'content': m.content,
                    'file_url': m.file_url,
                    'order': m.order,
                    'is_visible': m.is_visible,
                    'created_at': iso(m.created_at),
                }
                for m in Material.query.all()
            ],
            'submissions': [
                {
                    'id': s.id,
                    'task_id': s.task_id,
                    'student_id': s.student_id,
                    'content': s.content,
                    'file_url': s.file_url,
                    'submitted_at': iso(s.submitted_at),
                    'updated_at': iso(s.updated_at),
                    'score': s.score,
                    'comment': s.comment,
                    'graded_at': iso(s.graded_at),
                    'graded_by_id': s.graded_by_id,
                }
                for s in Submission.query.all()
            ],
        }

        with open('seed_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f'✅ Сохранено в seed_data.json:')
        print(f'   Пользователей: {len(data["users"])}')
        print(f'   Разделов:      {len(data["sections"])}')
        print(f'   Подразделов:   {len(data["subsections"])}')
        print(f'   Заданий:       {len(data["tasks"])}')
        print(f'   Материалов:    {len(data["materials"])}')
        print(f'   Ответов:       {len(data["submissions"])}')


if __name__ == '__main__':
    dump()

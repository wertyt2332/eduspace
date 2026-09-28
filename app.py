import json
import os
from datetime import datetime
from flask import Flask, render_template
from config import Config
from extensions import db, login_manager
from models import User, Section, Subsection, Task, Submission, Material  # noqa: F401
from blueprints.auth import auth_bp
from blueprints.main import main_bp
from blueprints.admin import admin_bp
from blueprints.teacher import teacher_bp
from blueprints.student import student_bp
from blueprints.profile import profile_bp


def load_seed_if_empty(app):
    """Если БД пуста — загружает данные из seed_data.json."""
    seed_path = os.path.join(app.root_path, 'seed_data.json')
    if not os.path.exists(seed_path):
        return

    if User.query.first():
        return  # база не пуста — ничего не делаем

    try:
        with open(seed_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f'[seed] Ошибка чтения seed_data.json: {e}')
        return

    def dt(s):
        return datetime.fromisoformat(s) if s else None

    try:
        # 1) Пользователи
        for u in data.get('users', []):
            db.session.add(User(
                id=u['id'],
                login=u['login'],
                password_hash=u['password_hash'],
                full_name=u['full_name'],
                role=u['role'],
                created_at=dt(u.get('created_at')),
            ))
        db.session.flush()

        # 2) Разделы
        for s in data.get('sections', []):
            db.session.add(Section(
                id=s['id'],
                title=s['title'],
                description=s.get('description', ''),
                is_visible=s.get('is_visible', True),
                created_at=dt(s.get('created_at')),
            ))
        db.session.flush()

        # 3) Связи раздел ↔ учитель/ученик
        for s in data.get('sections', []):
            section = db.session.get(Section, s['id'])
            for tid in s.get('teacher_ids', []):
                u = db.session.get(User, tid)
                if u:
                    section.teachers.append(u)
            for sid in s.get('student_ids', []):
                u = db.session.get(User, sid)
                if u:
                    section.students.append(u)
        db.session.flush()

        # 4) Подразделы
        for sub in data.get('subsections', []):
            db.session.add(Subsection(
                id=sub['id'],
                section_id=sub['section_id'],
                title=sub['title'],
                description=sub.get('description', ''),
                order=sub.get('order', 0),
                is_visible=sub.get('is_visible', True),
                created_at=dt(sub.get('created_at')),
            ))
        db.session.flush()

        # 5) Задания
        for t in data.get('tasks', []):
            db.session.add(Task(
                id=t['id'],
                subsection_id=t['subsection_id'],
                title=t['title'],
                description=t.get('description', ''),
                task_type=t['task_type'],
                max_score=t.get('max_score', 5),
                deadline=dt(t.get('deadline')),
                is_visible=t.get('is_visible', True),
                order=t.get('order', 0),
                options_json=t.get('options_json', '[]'),
                created_at=dt(t.get('created_at')),
            ))
        db.session.flush()

        # 6) Материалы
        for m in data.get('materials', []):
            db.session.add(Material(
                id=m['id'],
                subsection_id=m['subsection_id'],
                title=m['title'],
                material_type=m['material_type'],
                content=m.get('content', ''),
                file_url=m.get('file_url'),
                order=m.get('order', 0),
                is_visible=m.get('is_visible', True),
                created_at=dt(m.get('created_at')),
            ))
        db.session.flush()

        # 7) Ответы
        for s in data.get('submissions', []):
            db.session.add(Submission(
                id=s['id'],
                task_id=s['task_id'],
                student_id=s['student_id'],
                content=s.get('content', ''),
                file_url=s.get('file_url'),
                submitted_at=dt(s.get('submitted_at')),
                updated_at=dt(s.get('updated_at')),
                score=s.get('score'),
                comment=s.get('comment', ''),
                graded_at=dt(s.get('graded_at')),
                graded_by_id=s.get('graded_by_id'),
            ))

        db.session.commit()
        print(f'[seed] Восстановлено из seed_data.json:')
        print(f'       пользователей: {len(data.get("users", []))}')
        print(f'       разделов:      {len(data.get("sections", []))}')
        print(f'       заданий:       {len(data.get("tasks", []))}')

    except Exception as e:
        db.session.rollback()
        print(f'[seed] Ошибка загрузки: {e}')


def ensure_admin(app):
    login = app.config['ADMIN_LOGIN']
    if not User.query.filter_by(login=login).first():
        admin = User(login=login, full_name='Администратор', role='admin')
        admin.set_password(app.config['ADMIN_PASSWORD'])
        db.session.add(admin)
        db.session.commit()
        print(f'[init] Создан администратор: {login}')


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(profile_bp)

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.template_filter('from_json')
    def from_json_filter(value):
        import json
        try:
            return json.loads(value) if value else []
        except (ValueError, TypeError):
            return []

    with app.app_context():
        db.create_all()
        load_seed_if_empty(app)   # ← сначала пробуем восстановить
        ensure_admin(app)          # ← если админа нет — создаём

    @app.template_filter('video_embed')
    def video_embed_filter(url):
        """Превращает ссылку YouTube/Vimeo/RuTube в embed-URL."""
        import re
        url = (url or '').strip()
        m = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([\w-]{6,})', url)
        if m:
            return f'https://www.youtube.com/embed/{m.group(1)}'
        m = re.search(r'vimeo\.com/(\d+)', url)
        if m:
            return f'https://player.vimeo.com/video/{m.group(1)}'
        m = re.search(r'rutube\.ru/video/(\w+)', url)
        if m:
            return f'https://rutube.ru/play/embed/{m.group(1)}'
        return None

    return app


app = create_app()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

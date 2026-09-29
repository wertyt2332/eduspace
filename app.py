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


def bootstrap_database(app):
    """При старте: если БД пуста, восстанавливает данные.
    Порядок: Supabase → seed_data.json → создаёт админа.
    """
    from backup import load_from_supabase, load_from_local_file, restore_from_dict

    if User.query.first():
        return  # БД не пуста

    # 1) Supabase
    if app.config.get('SUPABASE_URL'):
        data, err = load_from_supabase()
        if data:
            try:
                stats = restore_from_dict(data, clear_first=False)
                print(f'[bootstrap] Восстановлено из Supabase: {stats}')
                return
            except Exception as e:
                print(f'[bootstrap] Ошибка восстановления из Supabase: {e}')
        else:
            print(f'[bootstrap] Supabase пуст или ошибка: {err}')

    # 2) seed_data.json
    seed_path = os.path.join(app.root_path, 'seed_data.json')
    data = load_from_local_file(seed_path)
    if data:
        try:
            stats = restore_from_dict(data, clear_first=False)
            print(f'[bootstrap] Восстановлено из seed_data.json: {stats}')
            return
        except Exception as e:
            print(f'[bootstrap] Ошибка восстановления из seed: {e}')


def start_autobackup(app, interval=300):
    """Фоновый поток: сохраняет бэкап в Supabase каждые N секунд."""
    import threading
    import time

    def loop():
        with app.app_context():
            while True:
                time.sleep(interval)
                try:
                    from backup import save_to_supabase
                    ok, err = save_to_supabase()
                    if ok:
                        print(f'[backup] Автобэкап в Supabase: OK', flush=True)
                    else:
                        print(f'[backup] Ошибка автобэкапа: {err}', flush=True)
                except Exception as e:
                    print(f'[backup] Исключение в автобэкапе: {e}', flush=True)

    t = threading.Thread(target=loop, daemon=True, name='autobackup')
    t.start()
    print(f'[backup] Автобэкап запущен (каждые {interval} сек)', flush=True)


def ensure_admin(app):
    """Создаёт админа из конфига, если его ещё нет."""
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

    @app.template_filter('video_embed')
    def video_embed_filter(url):
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

    with app.app_context():
        db.create_all()
        bootstrap_database(app)
        ensure_admin(app)

    # Автобэкап (не в reloader-процессе)
    if app.config.get('SUPABASE_URL'):
        import os
        if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            start_autobackup(app, interval=300)

    return app


app = create_app()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

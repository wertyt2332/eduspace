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

    with app.app_context():
        db.create_all()
        ensure_admin(app)

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

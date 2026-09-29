import csv
import io
import json
import secrets
import string
from functools import wraps
from flask import (
    Blueprint, render_template, abort, request,
    redirect, url_for, flash
)
from flask_login import login_required, current_user
from extensions import db
from models import User, Section, section_teachers, section_students

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def gen_password(length=8):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# ---------- Дашборд ----------

@admin_bp.route('/')
@admin_required
def dashboard():
    stats = {
        'sections': Section.query.count(),
        'teachers': User.query.filter_by(role='teacher').count(),
        'students': User.query.filter_by(role='student').count(),
    }
    return render_template('admin/dashboard.html', stats=stats)


# ---------- Пользователи ----------

@admin_bp.route('/users/<role>')
@admin_required
def users_list(role):
    if role not in ('teacher', 'student'):
        abort(404)
    users = User.query.filter_by(role=role).order_by(User.full_name).all()
    return render_template('admin/users_list.html', users=users, role=role)


@admin_bp.route('/users/<role>/new', methods=['GET', 'POST'])
@admin_required
def user_new(role):
    if role not in ('teacher', 'student'):
        abort(404)

    if request.method == 'POST':
        login = request.form.get('login', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '').strip() or gen_password()

        if not login or not full_name:
            flash('Логин и ФИО обязательны.', 'danger')
        elif User.query.filter_by(login=login).first():
            flash('Такой логин уже занят.', 'danger')
        else:
            user = User(login=login, full_name=full_name, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash(f'Создан {user.role_label.lower()} «{full_name}». Пароль: {password}', 'success')
            return redirect(url_for('admin.users_list', role=role))

    return render_template('admin/user_form.html', role=role, user=None)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def user_edit(user_id):
    user = db.session.get(User, user_id)
    if not user or user.is_admin:
        abort(404)

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        new_password = request.form.get('password', '').strip()

        if not full_name:
            flash('ФИО обязательно.', 'danger')
        else:
            user.full_name = full_name
            if new_password:
                user.set_password(new_password)
                flash(f'Пароль обновлён: {new_password}', 'info')
            db.session.commit()
            flash('Сохранено.', 'success')
            return redirect(url_for('admin.users_list', role=user.role))

    return render_template('admin/user_form.html', role=user.role, user=user)


@admin_bp.route('/users/<int:user_id>/reset_password', methods=['POST'])
@admin_required
def user_reset_password(user_id):
    user = db.session.get(User, user_id)
    if not user or user.is_admin:
        abort(404)
    new_password = gen_password()
    user.set_password(new_password)
    db.session.commit()
    flash(f'Новый пароль для {user.full_name}: {new_password}', 'info')
    return redirect(url_for('admin.users_list', role=user.role))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def user_delete(user_id):
    user = db.session.get(User, user_id)
    if not user or user.is_admin:
        abort(404)
    role = user.role
    db.session.delete(user)
    db.session.commit()
    flash('Пользователь удалён.', 'info')
    return redirect(url_for('admin.users_list', role=role))


# ---------- Разделы ----------

@admin_bp.route('/sections')
@admin_required
def sections_list():
    sections = Section.query.order_by(Section.title).all()
    return render_template('admin/sections_list.html', sections=sections)


@admin_bp.route('/sections/new', methods=['GET', 'POST'])
@admin_required
def section_new():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        if not title:
            flash('Название обязательно.', 'danger')
        else:
            section = Section(title=title, description=description)
            db.session.add(section)
            db.session.commit()
            flash(f'Раздел «{title}» создан.', 'success')
            return redirect(url_for('admin.sections_list'))
    return render_template('admin/section_form.html', section=None)


@admin_bp.route('/sections/<int:section_id>/edit', methods=['GET', 'POST'])
@admin_required
def section_edit(section_id):
    section = db.session.get(Section, section_id)
    if not section:
        abort(404)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        if not title:
            flash('Название обязательно.', 'danger')
        else:
            section.title = title
            section.description = description
            db.session.commit()
            flash('Сохранено.', 'success')
            return redirect(url_for('admin.sections_list'))

    return render_template('admin/section_form.html', section=section)


@admin_bp.route('/sections/<int:section_id>/toggle', methods=['POST'])
@admin_required
def section_toggle(section_id):
    section = db.session.get(Section, section_id)
    if not section:
        abort(404)
    section.is_visible = not section.is_visible
    db.session.commit()
    flash('Видимость раздела обновлена.', 'info')
    return redirect(url_for('admin.sections_list'))


@admin_bp.route('/sections/<int:section_id>/delete', methods=['POST'])
@admin_required
def section_delete(section_id):
    section = db.session.get(Section, section_id)
    if not section:
        abort(404)
    db.session.delete(section)
    db.session.commit()
    flash('Раздел удалён.', 'info')
    return redirect(url_for('admin.sections_list'))


@admin_bp.route('/sections/<int:section_id>/members', methods=['GET', 'POST'])
@admin_required
def section_members(section_id):
    section = db.session.get(Section, section_id)
    if not section:
        abort(404)

    if request.method == 'POST':
        teacher_ids = set(map(int, request.form.getlist('teachers')))
        student_ids = set(map(int, request.form.getlist('students')))

        all_teachers = User.query.filter_by(role='teacher').all()
        all_students = User.query.filter_by(role='student').all()

        section.teachers = [t for t in all_teachers if t.id in teacher_ids]
        section.students = [s for s in all_students if s.id in student_ids]
        db.session.commit()
        flash('Состав раздела обновлён.', 'success')
        return redirect(url_for('admin.sections_list'))

    all_teachers = User.query.filter_by(role='teacher').order_by(User.full_name).all()
    all_students = User.query.filter_by(role='student').order_by(User.full_name).all()

    return render_template(
        'admin/section_members.html',
        section=section,
        all_teachers=all_teachers,
        all_students=all_students,
    )


# ---------- CSV-импорт ----------

@admin_bp.route('/import', methods=['GET', 'POST'])
@admin_required
def import_csv():
    """
    Формат CSV (первая строка — заголовки, разделитель — запятая):
    full_name,login,password,role
    Иванов Иван,ivanov,,student
    Петрова Мария,petrova,pass123,teacher

    - password можно оставить пустым — сгенерируется автоматически
    - role: student | teacher
    """
    results = None
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename:
            flash('Выберите файл.', 'danger')
        else:
            try:
                content = file.read().decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(content))
                created, skipped = [], []
                for row in reader:
                    full_name = (row.get('full_name') or '').strip()
                    login = (row.get('login') or '').strip()
                    password = (row.get('password') or '').strip() or gen_password()
                    role = (row.get('role') or '').strip().lower()

                    if not full_name or not login or role not in ('student', 'teacher'):
                        skipped.append((login or '?', 'неверные поля'))
                        continue
                    if User.query.filter_by(login=login).first():
                        skipped.append((login, 'логин занят'))
                        continue

                    user = User(login=login, full_name=full_name, role=role)
                    user.set_password(password)
                    db.session.add(user)
                    created.append((full_name, login, password, role))

                db.session.commit()
                results = {'created': created, 'skipped': skipped}
                flash(f'Импорт завершён: создано {len(created)}, пропущено {len(skipped)}.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Ошибка чтения файла: {e}', 'danger')

    return render_template('admin/import.html', results=results)


# ---------- Impersonation (вход как пользователь) ----------

@admin_bp.route('/impersonate/<int:user_id>')
@admin_required
def impersonate(user_id):
    from flask import session
    from flask_login import login_user

    target = db.session.get(User, user_id)
    if not target or target.is_admin:
        abort(404)

    # запоминаем, кто был админом
    session['impersonator_id'] = current_user.id
    login_user(target)
    flash(f'Вы вошли как {target.full_name}. Не забудьте вернуться.', 'warning')
    return redirect(url_for('main.dashboard'))


@admin_bp.route('/stop_impersonate')
@login_required
def stop_impersonate():
    from flask import session
    from flask_login import login_user

    admin_id = session.pop('impersonator_id', None)
    if not admin_id:
        flash('Вы не в режиме impersonate.', 'danger')
        return redirect(url_for('main.dashboard'))

    admin = db.session.get(User, admin_id)
    if not admin or not admin.is_admin:
        flash('Не удалось вернуться.', 'danger')
        return redirect(url_for('auth.logout'))

    login_user(admin)
    flash('Возврат в админку.', 'success')
    return redirect(url_for('admin.dashboard'))\




# ---------- Резервное копирование ----------

@admin_bp.route('/backup')
@admin_required
def backup_page():
    return render_template('admin/backup.html')


@admin_bp.route('/backup/save_now', methods=['POST'])
@admin_required
def backup_save_now():
    from backup import save_to_supabase
    ok, err = save_to_supabase()
    if ok:
        flash('Бэкап сохранён в Supabase Storage.', 'success')
    else:
        flash(f'Ошибка: {err}', 'danger')
    return redirect(url_for('admin.backup_page'))


@admin_bp.route('/backup/download')
@admin_required
def backup_download():
    from flask import Response
    from backup import dump_to_dict
    from datetime import datetime as dt

    data = dump_to_dict()
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    filename = f'eduspace_backup_{dt.utcnow().strftime("%Y%m%d_%H%M")}.json'
    return Response(
        payload,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@admin_bp.route('/backup/upload', methods=['POST'])
@admin_required
def backup_upload():
    file = request.files.get('file')
    if not file or not file.filename:
        flash('Выберите файл.', 'danger')
        return redirect(url_for('admin.backup_page'))

    try:
        data = json.loads(file.read().decode('utf-8'))
    except Exception as e:
        flash(f'Ошибка чтения файла: {e}', 'danger')
        return redirect(url_for('admin.backup_page'))

    replace = request.form.get('replace') == 'on'

    try:
        from backup import restore_from_dict
        stats = restore_from_dict(data, clear_first=replace)
        flash(f'Импорт завершён: {stats}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка импорта: {e}', 'danger')

    return redirect(url_for('admin.backup_page'))

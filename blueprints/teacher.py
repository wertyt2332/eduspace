import json
from datetime import datetime
from functools import wraps
from flask import (
    Blueprint, render_template, abort, request,
    redirect, url_for, flash
)
from flask_login import login_required, current_user
from extensions import db
from models import User, Section, Subsection, Task, Submission, Material
from storage import save_file

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')


def teacher_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not (current_user.is_teacher or current_user.is_admin):
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def _own_section(section_id):
    section = db.session.get(Section, section_id)
    if not section:
        abort(404)
    if current_user.is_admin:
        return section
    if section not in current_user.taught_sections:
        abort(403)
    return section


def _own_subsection(subsection_id):
    sub = db.session.get(Subsection, subsection_id)
    if not sub:
        abort(404)
    _own_section(sub.section_id)
    return sub


def _own_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        abort(404)
    _own_subsection(task.subsection_id)
    return task


def _parse_deadline(value):
    value = (value or '').strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M')
    except ValueError:
        return None


def _parse_test_options(form):
    """Собирает варианты теста из формы."""
    texts = form.getlist('option_text')
    correct_indexes = set(map(int, form.getlist('option_correct')))
    options = []
    for i, t in enumerate(texts):
        t = t.strip()
        if not t:
            continue
        options.append({'text': t, 'correct': i in correct_indexes})
    return options


# ---------- Дашборд ----------

@teacher_bp.route('/')
@teacher_required
def dashboard():
    if current_user.is_admin:
        sections = Section.query.order_by(Section.title).all()
    else:
        sections = sorted(current_user.taught_sections, key=lambda s: s.title)
    return render_template('teacher/dashboard.html', sections=sections)


# ---------- Раздел: список подразделов ----------

@teacher_bp.route('/section/<int:section_id>')
@teacher_required
def section_view(section_id):
    section = _own_section(section_id)
    return render_template('teacher/section.html', section=section)


# ---------- Подразделы ----------

@teacher_bp.route('/section/<int:section_id>/subsection/new', methods=['GET', 'POST'])
@teacher_required
def subsection_new(section_id):
    section = _own_section(section_id)
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        if not title:
            flash('Название обязательно.', 'danger')
        else:
            order = (max([s.order for s in section.subsections], default=0) + 1)
            sub = Subsection(section_id=section.id, title=title,
                             description=description, order=order)
            db.session.add(sub)
            db.session.commit()
            flash('Подраздел создан.', 'success')
            return redirect(url_for('teacher.section_view', section_id=section.id))
    return render_template('teacher/subsection_form.html', section=section, sub=None)


@teacher_bp.route('/subsection/<int:subsection_id>/edit', methods=['GET', 'POST'])
@teacher_required
def subsection_edit(subsection_id):
    sub = _own_subsection(subsection_id)
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        if not title:
            flash('Название обязательно.', 'danger')
        else:
            sub.title = title
            sub.description = description
            db.session.commit()
            flash('Сохранено.', 'success')
            return redirect(url_for('teacher.section_view', section_id=sub.section_id))
    return render_template('teacher/subsection_form.html', section=sub.section, sub=sub)


@teacher_bp.route('/subsection/<int:subsection_id>/toggle', methods=['POST'])
@teacher_required
def subsection_toggle(subsection_id):
    sub = _own_subsection(subsection_id)
    sub.is_visible = not sub.is_visible
    db.session.commit()
    flash('Видимость обновлена.', 'info')
    return redirect(url_for('teacher.section_view', section_id=sub.section_id))


@teacher_bp.route('/subsection/<int:subsection_id>/delete', methods=['POST'])
@teacher_required
def subsection_delete(subsection_id):
    sub = _own_subsection(subsection_id)
    section_id = sub.section_id
    db.session.delete(sub)
    db.session.commit()
    flash('Подраздел удалён.', 'info')
    return redirect(url_for('teacher.section_view', section_id=section_id))


# ---------- Задания ----------

@teacher_bp.route('/subsection/<int:subsection_id>/task/new', methods=['GET', 'POST'])
@teacher_required
def task_new(subsection_id):
    sub = _own_subsection(subsection_id)
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        task_type = request.form.get('task_type', 'text')
        max_score = request.form.get('max_score', '5')
        deadline_raw = request.form.get('deadline', '')

        if not title:
            flash('Название обязательно.', 'danger')
        elif task_type not in ('text', 'file', 'test', 'link'):
            flash('Неверный тип задания.', 'danger')
        else:
            try:
                max_score = int(max_score)
                if max_score < 1:
                    max_score = 5
            except ValueError:
                max_score = 5

            options_json = '[]'
            if task_type == 'test':
                options = _parse_test_options(request.form)
                if len(options) < 2:
                    flash('В тесте нужно минимум 2 варианта.', 'danger')
                    return render_template('teacher/task_form.html', section=sub.section, sub=sub, task=None)
                if not any(o['correct'] for o in options):
                    flash('Отметьте хотя бы один правильный вариант.', 'danger')
                    return render_template('teacher/task_form.html', section=sub.section, sub=sub, task=None)
                options_json = json.dumps(options, ensure_ascii=False)

            order = max([t.order for t in sub.tasks], default=0) + 1
            task = Task(
                subsection_id=sub.id,
                title=title,
                description=description,
                task_type=task_type,
                max_score=max_score,
                deadline=_parse_deadline(deadline_raw),
                options_json=options_json,
                order=order,
            )
            db.session.add(task)
            db.session.commit()
            flash('Задание создано.', 'success')
            return redirect(url_for('teacher.subsection_view', subsection_id=sub.id))

    return render_template('teacher/task_form.html', section=sub.section, sub=sub, task=None)


@teacher_bp.route('/task/<int:task_id>/edit', methods=['GET', 'POST'])
@teacher_required
def task_edit(task_id):
    task = _own_task(task_id)
    sub = task.subsection

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        task_type = request.form.get('task_type', task.task_type)
        max_score = request.form.get('max_score', str(task.max_score))
        deadline_raw = request.form.get('deadline', '')

        if not title:
            flash('Название обязательно.', 'danger')
        elif task_type not in ('text', 'file', 'test', 'link'):
            flash('Неверный тип.', 'danger')
        else:
            try:
                max_score = int(max_score)
                if max_score < 1:
                    max_score = 5
            except ValueError:
                max_score = 5

            task.title = title
            task.description = description
            task.task_type = task_type
            task.max_score = max_score
            task.deadline = _parse_deadline(deadline_raw)

            if task_type == 'test':
                options = _parse_test_options(request.form)
                if len(options) >= 2 and any(o['correct'] for o in options):
                    task.options_json = json.dumps(options, ensure_ascii=False)
                else:
                    flash('Тест: нужно минимум 2 варианта и хотя бы один правильный.', 'danger')
                    return redirect(url_for('teacher.task_edit', task_id=task.id))
            else:
                task.options_json = '[]'

            db.session.commit()
            flash('Задание сохранено.', 'success')
            return redirect(url_for('teacher.subsection_view', subsection_id=sub.id))

    return render_template('teacher/task_form.html', section=sub.section, sub=sub, task=task)


@teacher_bp.route('/task/<int:task_id>/toggle', methods=['POST'])
@teacher_required
def task_toggle(task_id):
    task = _own_task(task_id)
    task.is_visible = not task.is_visible
    db.session.commit()
    flash('Видимость задания обновлена.', 'info')
    return redirect(url_for('teacher.subsection_view', subsection_id=task.subsection_id))


@teacher_bp.route('/task/<int:task_id>/delete', methods=['POST'])
@teacher_required
def task_delete(task_id):
    task = _own_task(task_id)
    sub_id = task.subsection_id
    db.session.delete(task)
    db.session.commit()
    flash('Задание удалено.', 'info')
    return redirect(url_for('teacher.subsection_view', subsection_id=sub_id))


# ---------- Просмотр подраздела и заданий ----------

@teacher_bp.route('/subsection/<int:subsection_id>')
@teacher_required
def subsection_view(subsection_id):
    sub = _own_subsection(subsection_id)
    return render_template('teacher/subsection_view.html', section=sub.section, sub=sub)


@teacher_bp.route('/task/<int:task_id>')
@teacher_required
def task_view(task_id):
    task = _own_task(task_id)
    submissions = (
        Submission.query
        .filter_by(task_id=task.id)
        .join(User, Submission.student_id == User.id)
        .order_by(User.full_name)
        .all()
    )
    # ещё не сдавшие
    all_students = task.subsection.section.students
    submitted_ids = {s.student_id for s in submissions}
    not_submitted = [s for s in all_students if s.id not in submitted_ids]

    options = json.loads(task.options_json or '[]')

    return render_template(
        'teacher/task_view.html',
        section=task.subsection.section,
        sub=task.subsection,
        task=task,
        submissions=submissions,
        not_submitted=not_submitted,
        options=options,
    )


# ---------- Оценки ----------

@teacher_bp.route('/submission/<int:submission_id>/grade', methods=['POST'])
@teacher_required
def grade_submission(submission_id):
    submission = db.session.get(Submission, submission_id)
    if not submission:
        abort(404)
    _own_task(submission.task_id)

    score_raw = request.form.get('score', '').strip()
    comment = request.form.get('comment', '').strip()

    try:
        score = int(score_raw) if score_raw else None
    except ValueError:
        score = None

    if score is not None and score < 0:
        score = 0
    if score is not None and score > submission.task.max_score:
        score = submission.task.max_score

    submission.score = score
    submission.comment = comment
    submission.graded_at = datetime.utcnow()
    submission.graded_by_id = current_user.id
    db.session.commit()
    flash('Оценка сохранена.', 'success')
    return redirect(url_for('teacher.task_view', task_id=submission.task_id))


# ---------- Состав раздела (ученики) ----------

@teacher_bp.route('/section/<int:section_id>/students', methods=['GET', 'POST'])
@teacher_required
def section_students(section_id):
    section = _own_section(section_id)

    if request.method == 'POST':
        student_ids = set(map(int, request.form.getlist('students')))
        all_students = User.query.filter_by(role='student').all()
        section.students = [s for s in all_students if s.id in student_ids]
        db.session.commit()
        flash('Состав учеников обновлён.', 'success')
        return redirect(url_for('teacher.section_view', section_id=section.id))

    all_students = User.query.filter_by(role='student').order_by(User.full_name).all()
    return render_template(
        'teacher/section_students.html',
        section=section,
        all_students=all_students,
    )



# ---------- Материалы ----------

def _own_material(material_id):
    material = db.session.get(Material, material_id)
    if not material:
        abort(404)
    _own_subsection(material.subsection_id)
    return material


@teacher_bp.route('/subsection/<int:subsection_id>/material/new', methods=['GET', 'POST'])
@teacher_required
def material_new(subsection_id):
    sub = _own_subsection(subsection_id)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        material_type = request.form.get('material_type', 'text')
        content = (request.form.get('content') or '').strip()

        if not title:
            flash('Название обязательно.', 'danger')
            return redirect(url_for('teacher.material_new', subsection_id=sub.id))

        if material_type not in ('text', 'video', 'link', 'file'):
            flash('Неверный тип материала.', 'danger')
            return redirect(url_for('teacher.material_new', subsection_id=sub.id))

        file_url = None
        if material_type == 'file':
            uploaded = request.files.get('file')
            if not uploaded or not uploaded.filename:
                flash('Загрузите файл.', 'danger')
                return redirect(url_for('teacher.material_new', subsection_id=sub.id))
            try:
                file_url = save_file(uploaded)
            except ValueError as e:
                flash(str(e), 'danger')
                return redirect(url_for('teacher.material_new', subsection_id=sub.id))
        elif not content:
            flash('Введите содержимое.', 'danger')
            return redirect(url_for('teacher.material_new', subsection_id=sub.id))

        order = max([m.order for m in sub.materials], default=0) + 1
        mat = Material(
            subsection_id=sub.id,
            title=title,
            material_type=material_type,
            content=content,
            file_url=file_url,
            order=order,
        )
        db.session.add(mat)
        db.session.commit()
        flash('Материал добавлен.', 'success')
        return redirect(url_for('teacher.subsection_view', subsection_id=sub.id))

    return render_template('teacher/material_form.html', section=sub.section, sub=sub, material=None)


@teacher_bp.route('/material/<int:material_id>/edit', methods=['GET', 'POST'])
@teacher_required
def material_edit(material_id):
    mat = _own_material(material_id)
    sub = mat.subsection

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        material_type = request.form.get('material_type', mat.material_type)
        content = (request.form.get('content') or '').strip()

        if not title:
            flash('Название обязательно.', 'danger')
            return redirect(url_for('teacher.material_edit', material_id=mat.id))

        if material_type not in ('text', 'video', 'link', 'file'):
            flash('Неверный тип.', 'danger')
            return redirect(url_for('teacher.material_edit', material_id=mat.id))

        mat.title = title
        mat.material_type = material_type

        if material_type == 'file':
            uploaded = request.files.get('file')
            if uploaded and uploaded.filename:
                try:
                    mat.file_url = save_file(uploaded)
                except ValueError as e:
                    flash(str(e), 'danger')
                    return redirect(url_for('teacher.material_edit', material_id=mat.id))
            mat.content = ''
        else:
            if not content:
                flash('Введите содержимое.', 'danger')
                return redirect(url_for('teacher.material_edit', material_id=mat.id))
            mat.content = content
            mat.file_url = None

        db.session.commit()
        flash('Материал сохранён.', 'success')
        return redirect(url_for('teacher.subsection_view', subsection_id=sub.id))

    return render_template('teacher/material_form.html', section=sub.section, sub=sub, material=mat)


@teacher_bp.route('/material/<int:material_id>/toggle', methods=['POST'])
@teacher_required
def material_toggle(material_id):
    mat = _own_material(material_id)
    mat.is_visible = not mat.is_visible
    db.session.commit()
    flash('Видимость обновлена.', 'info')
    return redirect(url_for('teacher.subsection_view', subsection_id=mat.subsection_id))


@teacher_bp.route('/material/<int:material_id>/delete', methods=['POST'])
@teacher_required
def material_delete(material_id):
    mat = _own_material(material_id)
    sub_id = mat.subsection_id
    db.session.delete(mat)
    db.session.commit()
    flash('Материал удалён.', 'info')
    return redirect(url_for('teacher.subsection_view', subsection_id=sub_id))

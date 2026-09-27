import json
import os
import uuid
from datetime import datetime
from functools import wraps
from flask import (
    Blueprint, render_template, abort, request,
    redirect, url_for, flash, current_app
)
from flask_login import login_required, current_user
from storage import save_file
from extensions import db
from models import User, Section, Subsection, Task, Submission

student_bp = Blueprint('student', __name__, url_prefix='/student')

ALLOWED_EXT = {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt',
               'jpg', 'jpeg', 'png', 'gif', 'webp', 'heic'}


def student_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_student:
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def _enrolled_section(section_id):
    section = db.session.get(Section, section_id)
    if not section or not section.is_visible:
        abort(404)
    if section not in current_user.enrolled_sections:
        abort(403)
    return section


def _enrolled_subsection(sub_id):
    sub = db.session.get(Subsection, sub_id)
    if not sub or not sub.is_visible:
        abort(404)
    _enrolled_section(sub.section_id)
    return sub


def _enrolled_task(task_id):
    task = db.session.get(Task, task_id)
    if not task or not task.is_visible:
        abort(404)
    _enrolled_subsection(task.subsection_id)
    return task



def _is_overdue(task):
    return task.deadline is not None and datetime.utcnow() > task.deadline


def _grade_test(task, selected_indexes):
    """Автопроверка теста."""
    options = json.loads(task.options_json or '[]')
    correct = {i for i, o in enumerate(options) if o.get('correct')}
    selected = set(selected_indexes)
    if correct and correct == selected:
        return task.max_score
    return 0


# ---------- Дашборд ----------

@student_bp.route('/')
@student_required
def dashboard():
    sections = [s for s in current_user.enrolled_sections if s.is_visible]
    sections.sort(key=lambda s: s.title)
    return render_template('student/dashboard.html', sections=sections)


# ---------- Раздел ----------

@student_bp.route('/section/<int:section_id>')
@student_required
def section_view(section_id):
    section = _enrolled_section(section_id)
    subs = [s for s in section.subsections if s.is_visible]
    return render_template('student/section.html', section=section, subs=subs)


# ---------- Подраздел ----------

@student_bp.route('/subsection/<int:subsection_id>')
@student_required
def subsection_view(subsection_id):
    sub = _enrolled_subsection(subsection_id)
    tasks = [t for t in sub.tasks if t.is_visible]
    materials = [m for m in sub.materials if m.is_visible]

    my_subs = {
        s.task_id: s for s in Submission.query
        .filter_by(student_id=current_user.id)
        .filter(Submission.task_id.in_([t.id for t in tasks] or [0]))
        .all()
    }

    return render_template(
        'student/subsection.html',
        section=sub.section,
        sub=sub,
        tasks=tasks,
        materials=materials,
        my_subs=my_subs,
        is_overdue=_is_overdue,
    )



# ---------- Задание ----------

@student_bp.route('/task/<int:task_id>', methods=['GET', 'POST'])
@student_required
def task_view(task_id):
    task = _enrolled_task(task_id)
    sub = task.subsection
    section = sub.section

    submission = Submission.query.filter_by(
        task_id=task.id, student_id=current_user.id
    ).first()

    options = json.loads(task.options_json or '[]')
    overdue = _is_overdue(task)
    graded = submission is not None and submission.score is not None
    locked = overdue or graded  # редактирование запрещено

    if request.method == 'POST':
        if locked:
            flash('Это задание уже нельзя изменить.', 'warning')
            return redirect(url_for('student.task_view', task_id=task.id))

        try:
            content = ''
            file_url = submission.file_url if submission else None

            if task.task_type == 'text':
                content = (request.form.get('content') or '').strip()
                if not content:
                    flash('Введите ответ.', 'danger')
                    return redirect(url_for('student.task_view', task_id=task.id))

            elif task.task_type == 'link':
                content = (request.form.get('link') or '').strip()
                if not content:
                    flash('Введите ссылку.', 'danger')
                    return redirect(url_for('student.task_view', task_id=task.id))

            elif task.task_type == 'file':
                uploaded = request.files.get('file')
                if uploaded and uploaded.filename:
                    file_url = save_file(uploaded)
                elif not file_url:
                    flash('Загрузите файл.', 'danger')
                    return redirect(url_for('student.task_view', task_id=task.id))

            elif task.task_type == 'test':
                selected = list(map(int, request.form.getlist('answer')))
                if not selected:
                    flash('Выберите хотя бы один вариант.', 'danger')
                    return redirect(url_for('student.task_view', task_id=task.id))
                content = json.dumps(sorted(selected))

            # создаём или обновляем
            if submission is None:
                submission = Submission(
                    task_id=task.id, student_id=current_user.id
                )
                db.session.add(submission)

            submission.content = content
            submission.file_url = file_url
            submission.submitted_at = datetime.utcnow()

            # автопроверка теста
            if task.task_type == 'test':
                submission.score = _grade_test(task, selected)
                submission.comment = 'Автопроверка'
                submission.graded_at = datetime.utcnow()
                submission.graded_by_id = None

            db.session.commit()
            flash('Ответ сохранён.', 'success')
            return redirect(url_for('student.subsection_view', subsection_id=sub.id))

        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('student.task_view', task_id=task.id))

    return render_template(
        'student/task.html',
        section=section,
        sub=sub,
        task=task,
        submission=submission,
        options=options,
        overdue=overdue,
        graded=graded,
        locked=locked,
    )


# ---------- Мои оценки ----------

@student_bp.route('/grades')
@student_required
def grades():
    subs = (
        Submission.query
        .filter_by(student_id=current_user.id)
        .join(Task, Submission.task_id == Task.id)
        .order_by(Task.subsection_id, Task.order)
        .all()
    )

    # группируем по разделам
    by_section = {}
    total_score = 0
    total_max = 0
    graded_count = 0

    for s in subs:
        sec = s.task.subsection.section
        by_section.setdefault(sec, []).append(s)
        if s.score is not None:
            total_score += s.score
            total_max += s.task.max_score
            graded_count += 1

    avg_percent = round(total_score / total_max * 100, 1) if total_max else None

    return render_template(
        'student/grades.html',
        by_section=by_section,
        avg_percent=avg_percent,
        total_score=total_score,
        total_max=total_max,
        graded_count=graded_count,
    )

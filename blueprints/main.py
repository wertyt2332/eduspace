from flask import Blueprint, redirect, url_for
from flask_login import login_required, current_user

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin.dashboard'))
    if current_user.is_teacher:
        return redirect(url_for('teacher.dashboard'))
    return redirect(url_for('student.dashboard'))

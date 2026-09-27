from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db

profile_bp = Blueprint('profile', __name__, url_prefix='/profile')


@profile_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')

        if not current_user.check_password(current_password):
            flash('Текущий пароль неверный.', 'danger')
        elif len(new_password) < 6:
            flash('Новый пароль должен быть не короче 6 символов.', 'danger')
        elif new_password != confirm:
            flash('Пароли не совпадают.', 'danger')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Пароль успешно изменён.', 'success')
            return redirect(url_for('profile.index'))

    return render_template('profile/index.html')

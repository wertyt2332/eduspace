from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        login = request.form.get('login', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(login=login).first()
        if user and user.check_password(password):
            login_user(user, remember=bool(request.form.get('remember')))
            return redirect(url_for('main.dashboard'))
        flash('Неверный логин или пароль.', 'danger')
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('auth.login'))

from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, login_manager


section_teachers = db.Table(
    'section_teachers',
    db.Column('section_id', db.Integer, db.ForeignKey('section.id'), primary_key=True),
    db.Column('user_id',    db.Integer, db.ForeignKey('user.id'),    primary_key=True),
)

section_students = db.Table(
    'section_students',
    db.Column('section_id', db.Integer, db.ForeignKey('section.id'), primary_key=True),
    db.Column('user_id',    db.Integer, db.ForeignKey('user.id'),    primary_key=True),
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin | teacher | student
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    taught_sections = db.relationship('Section', secondary=section_teachers, backref='teachers')
    enrolled_sections = db.relationship('Section', secondary=section_students, backref='students')

    submissions = db.relationship(
        'Submission', foreign_keys='Submission.student_id',
        backref='student', cascade='all, delete-orphan'
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):   return self.role == 'admin'
    @property
    def is_teacher(self): return self.role == 'teacher'
    @property
    def is_student(self): return self.role == 'student'

    @property
    def role_label(self):
        return {'admin': 'Админ', 'teacher': 'Учитель', 'student': 'Ученик'}.get(self.role, self.role)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Section(db.Model):
    """Раздел. Создаётся только админом."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    is_visible = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subsections = db.relationship(
        'Subsection', backref='section',
        cascade='all, delete-orphan', order_by='Subsection.order'
    )


class Subsection(db.Model):
    """Подраздел. Редактируется учителем."""
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey('section.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    order = db.Column(db.Integer, default=0)
    is_visible = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship(
        'Task', backref='subsection',
        cascade='all, delete-orphan', order_by='Task.order'
    )

    materials = db.relationship(
        'Material', backref='subsection',
        cascade='all, delete-orphan', order_by='Material.order'
    )



class Task(db.Model):
    """Задание. Типы: text | file | test | link."""
    id = db.Column(db.Integer, primary_key=True)
    subsection_id = db.Column(db.Integer, db.ForeignKey('subsection.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    task_type = db.Column(db.String(20), nullable=False)
    max_score = db.Column(db.Integer, default=5)
    deadline = db.Column(db.DateTime, nullable=True)   # None = без дедлайна
    is_visible = db.Column(db.Boolean, default=True)
    order = db.Column(db.Integer, default=0)
    options_json = db.Column(db.Text, default='[]')    # для task_type == 'test'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    submissions = db.relationship(
        'Submission', backref='task', cascade='all, delete-orphan'
    )


class Submission(db.Model):
    """Ответ ученика на задание."""
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, default='')            # текст / url / выбранный ответ
    file_url = db.Column(db.String(500), nullable=True) # ссылка на файл в Supabase
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    score = db.Column(db.Integer, nullable=True)
    comment = db.Column(db.Text, default='')
    graded_at = db.Column(db.DateTime, nullable=True)
    graded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)



class Material(db.Model):
    """Материал: текст / видео / ссылка / файл. Не оценивается."""
    id = db.Column(db.Integer, primary_key=True)
    subsection_id = db.Column(db.Integer, db.ForeignKey('subsection.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    material_type = db.Column(db.String(20), nullable=False)  # text | video | link | file
    content = db.Column(db.Text, default='')       # для text/link/video — тут URL или текст
    file_url = db.Column(db.String(500), nullable=True)
    order = db.Column(db.Integer, default=0)
    is_visible = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

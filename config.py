import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-me')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///edu.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ADMIN_LOGIN = os.getenv('ADMIN_LOGIN', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

    SUPABASE_URL = os.getenv('SUPABASE_URL', '')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')
    SUPABASE_BUCKET = os.getenv('SUPABASE_BUCKET', 'uploads')

    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB

        # Quill-редактор
    QUILL_ENABLED = True

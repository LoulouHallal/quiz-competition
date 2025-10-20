import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DATABASE_URL = os.environ.get('DATABASE_URL') or 'postgresql://postgres:1234@localhost:5432/quiz_competition'
    PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL') or 'http://localhost:5000'
    SOCKETIO_MESSAGE_QUEUE = os.environ.get('SOCKETIO_MESSAGE_QUEUE')
    
    # CORS settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'https://localhost:3000,http://localhost:3000').split(',')
    
    # Session settings
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = False  # Allow JavaScript access for debugging
    SESSION_COOKIE_SAMESITE = None  # Allow cross-origin cookies for development
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    REMEMBER_COOKIE_DURATION = 86400  # 24 hours
    
    # File paths
    QR_CODE_DIR = os.path.join(os.path.dirname(__file__), 'static', 'qr')
    
    @staticmethod
    def init_app(app):
        os.makedirs(Config.QR_CODE_DIR, exist_ok=True)

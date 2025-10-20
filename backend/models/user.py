from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from models.database import db

class User(UserMixin):
    def __init__(self, user_id, user_fname, user_lname, user_email, userrole_id):
        self.id = user_id
        self.user_fname = user_fname
        self.user_lname = user_lname
        self.user_email = user_email
        self.userrole_id = userrole_id
    
    @staticmethod
    def get_by_id(user_id):
        """Fetch user by ID."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT user_id, user_fname, user_lname, user_email, userrole_id
                FROM app_user WHERE user_id = %s
            """, (user_id,))
            row = cursor.fetchone()
            if row:
                return User(row['user_id'], row['user_fname'], row['user_lname'], 
                           row['user_email'], row['userrole_id'])
        return None
    
    @staticmethod
    def get_by_email(email):
        """Fetch user by email."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT user_id, user_fname, user_lname, user_email, userrole_id
                FROM app_user WHERE user_email = %s
            """, (email,))
            row = cursor.fetchone()
            if row:
                return User(row['user_id'], row['user_fname'], row['user_lname'], 
                           row['user_email'], row['userrole_id'])
        return None
    
    @staticmethod
    def create_user(fname, lname, email, phone=None, role_id=2):
        """Create a new user (default role_id=2 for teacher)."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO app_user (user_fname, user_lname, user_email, user_phone, userrole_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING user_id
            """, (fname, lname, email, phone, role_id))
            result = cursor.fetchone()
            return result['user_id'] if result else None
    
    def to_dict(self):
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'email': self.user_email,
            'name': f"{self.user_fname} {self.user_lname}",
            'firstName': self.user_fname,
            'lastName': self.user_lname
        }

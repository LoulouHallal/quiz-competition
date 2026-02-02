from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from models.database import db

class User(UserMixin):
    def __init__(self, user_id, user_fname, user_lname, user_email, userrole_id, user_password=None):
        self.id = user_id
        self.user_fname = user_fname
        self.user_lname = user_lname
        self.user_email = user_email
        self.userrole_id = userrole_id
        self.user_password = user_password  # Hashed password
    
    @staticmethod
    def get_by_id(user_id):
        """Fetch user by ID."""
        try:
            with db.get_cursor() as cursor:
                cursor.execute("""
                    SELECT user_id, user_fname, user_lname, user_email, userrole_id, user_password
                    FROM app_user WHERE user_id = %s
                """, (user_id,))
                row = cursor.fetchone()
                if row:
                    return User(
                        row['user_id'], 
                        row['user_fname'], 
                        row['user_lname'],
                        row['user_email'], 
                        row['userrole_id'],
                        row.get('user_password')
                    )
        except Exception as e:
            print(f"ERROR in User.get_by_id: {e}")
        return None
    
    @staticmethod
    def get_by_email(email):
        """Fetch user by email."""
        try:
            with db.get_cursor() as cursor:
                cursor.execute("""
                    SELECT user_id, user_fname, user_lname, user_email, userrole_id, user_password
                    FROM app_user WHERE user_email = %s
                """, (email,))
                row = cursor.fetchone()
                if row:
                    return User(
                        row['user_id'], 
                        row['user_fname'], 
                        row['user_lname'],
                        row['user_email'], 
                        row['userrole_id'],
                        row.get('user_password')
                    )
        except Exception as e:
            print(f"ERROR in User.get_by_email: {e}")
        return None
    
    @staticmethod
    def create_user(fname, lname, email, password=None, phone=None, role_id=2):
        """
        Create a new user.
        
        Args:
            fname: First name
            lname: Last name
            email: Email address
            password: Plain text password (will be hashed)
            phone: Optional phone number
            role_id: User role (default 2 for teacher, 1 for student)
        
        Returns:
            user_id if successful, None otherwise
        """
        try:
            # Hash password if provided
            hashed_password = generate_password_hash(password) if password else None
            
            with db.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO app_user (user_fname, user_lname, user_email, user_phone, userrole_id, user_password)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING user_id
                """, (fname, lname, email, phone, role_id, hashed_password))
                result = cursor.fetchone()
                
                if result:
                    print(f"DEBUG: Created user {email} with id {result['user_id']}")
                    return result['user_id']
        except Exception as e:
            print(f"ERROR in User.create_user: {e}")
            import traceback
            traceback.print_exc()
        
        return None
    
    def verify_password(self, password):
        """Verify a plain text password against the stored hash."""
        if not self.user_password:
            print(f"WARNING: User {self.user_email} has no password hash")
            return False
        
        try:
            result = check_password_hash(self.user_password, password)
            if not result:
                print(f"DEBUG: Password verification failed for {self.user_email}")
            return result
        except Exception as e:
            print(f"ERROR: Password verification failed for {self.user_email}: {e}")
            return False
    
    def set_password(self, password):
        """Hash and set a new password."""
        try:
            self.user_password = generate_password_hash(password)
            
            # Update in database
            with db.get_cursor() as cursor:
                cursor.execute("""
                    UPDATE app_user SET user_password = %s WHERE user_id = %s
                """, (self.user_password, self.id))
            
            print(f"DEBUG: Password updated for user {self.user_email}")
            return True
        except Exception as e:
            print(f"ERROR setting password for {self.user_email}: {e}")
            return False
    
    def to_dict(self):
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'email': self.user_email,
            'name': f"{self.user_fname} {self.user_lname}",
            'firstName': self.user_fname,
            'lastName': self.user_lname
        }
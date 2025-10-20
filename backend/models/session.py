from models.database import db
import random
import string
from datetime import datetime

class Session:
    @staticmethod
    def generate_code(length=6):
        """Generate a random session code."""
        return ''.join(random.choices(string.digits, k=length))
    
    @staticmethod
    def create(course_id, class_name, settings=None):
        """Create a new session."""
        code = Session.generate_code()
        # Ensure unique code
        with db.get_cursor() as cursor:
            while True:
                cursor.execute("SELECT class_id FROM class_session WHERE class_code = %s", (code,))
                if not cursor.fetchone():
                    break
                code = Session.generate_code()
            
            cursor.execute("""
                INSERT INTO class_session (class_name, class_code, course_id, status, settings)
                VALUES (%s, %s, %s, 'lobby', %s)
                RETURNING class_id, class_code
            """, (class_name, code, course_id, settings or '{}'))
            result = cursor.fetchone()
            return result
    
    @staticmethod
    def get_by_id(class_id):
        """Get session by ID."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT class_id, class_name, class_link, class_code, course_id,
                       status, started_at, ended_at, current_question_index, settings, created_at
                FROM class_session
                WHERE class_id = %s
            """, (class_id,))
            return cursor.fetchone()
    
    @staticmethod
    def get_by_code(code):
        """Get session by code."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT class_id, class_name, class_link, class_code, course_id,
                       status, started_at, ended_at, current_question_index, settings, created_at
                FROM class_session
                WHERE class_code = %s
            """, (code,))
            return cursor.fetchone()
    
    @staticmethod
    def update_status(class_id, status):
        """Update session status."""
        with db.get_cursor() as cursor:
            updates = {'status': status}
            if status == 'active' and not Session.get_by_id(class_id).get('started_at'):
                cursor.execute("""
                    UPDATE class_session
                    SET status = %s, started_at = NOW()
                    WHERE class_id = %s
                """, (status, class_id))
            elif status == 'ended':
                cursor.execute("""
                    UPDATE class_session
                    SET status = %s, ended_at = NOW()
                    WHERE class_id = %s
                """, (status, class_id))
            else:
                cursor.execute("""
                    UPDATE class_session
                    SET status = %s
                    WHERE class_id = %s
                """, (status, class_id))
            return cursor.rowcount > 0
    
    @staticmethod
    def set_current_question(class_id, question_index):
        """Set the current question index."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                UPDATE class_session
                SET current_question_index = %s
                WHERE class_id = %s
            """, (question_index, class_id))
            return cursor.rowcount > 0
    
    @staticmethod
    def add_question_to_session(class_id, question_id, display_order):
        """Add a question to the session."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO class_question (class_id, question_id, display_order)
                VALUES (%s, %s, %s)
                ON CONFLICT (class_id, question_id) DO UPDATE SET display_order = EXCLUDED.display_order
                RETURNING class_question_id
            """, (class_id, question_id, display_order))
            result = cursor.fetchone()
            return result['class_question_id'] if result else None
    
    @staticmethod
    def get_session_questions(class_id):
        """Get all questions for a session in order."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT cq.class_question_id, cq.question_id, cq.display_order, 
                       cq.is_active, cq.locked_at,
                       q.question_content, q.points, q.time_limit_seconds
                FROM class_question cq
                JOIN question q ON q.question_id = cq.question_id
                WHERE cq.class_id = %s
                ORDER BY cq.display_order
            """, (class_id,))
            questions = cursor.fetchall()
            
            for question in questions:
                cursor.execute("""
                    SELECT answer_id, answer_content, display_order
                    FROM answers
                    WHERE question_id = %s
                    ORDER BY display_order
                """, (question['question_id'],))
                question['answers'] = cursor.fetchall()
            
            return questions
    
    @staticmethod
    def set_active_question(class_id, question_id):
        """Set a question as active (deactivate others)."""
        with db.get_cursor() as cursor:
            # Deactivate all questions
            cursor.execute("""
                UPDATE class_question
                SET is_active = FALSE
                WHERE class_id = %s
            """, (class_id,))
            
            # Activate the specified question
            cursor.execute("""
                UPDATE class_question
                SET is_active = TRUE
                WHERE class_id = %s AND question_id = %s
            """, (class_id, question_id))
            return cursor.rowcount > 0
    
    @staticmethod
    def lock_question(class_id, question_id):
        """Lock a question (no more answers accepted)."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                UPDATE class_question
                SET locked_at = NOW(), is_active = FALSE
                WHERE class_id = %s AND question_id = %s
            """, (class_id, question_id))
            return cursor.rowcount > 0

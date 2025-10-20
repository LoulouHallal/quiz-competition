from models.database import db
import json

class Quiz:
    @staticmethod
    def create(user_id, course_name):
        """Create a new quiz (course)."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO course (course_name, user_id)
                VALUES (%s, %s)
                RETURNING course_id
            """, (course_name, user_id))
            result = cursor.fetchone()
            return result['course_id'] if result else None
    
    @staticmethod
    def get_by_id(course_id):
        """Get quiz by ID with all questions."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT c.course_id, c.course_name, c.user_id, c.created_at
                FROM course c
                WHERE c.course_id = %s
            """, (course_id,))
            quiz = cursor.fetchone()
            
            if not quiz:
                return None
            
            # Get questions
            cursor.execute("""
                SELECT q.question_id, q.question_content, q.questiontype_id, 
                       q.points, q.time_limit_seconds, q.created_at
                FROM question q
                WHERE q.course_id = %s
                ORDER BY q.question_id
            """, (course_id,))
            questions = cursor.fetchall()
            
            # Get answers for each question
            for question in questions:
                cursor.execute("""
                    SELECT answer_id, answer_content, is_correct, display_order
                    FROM answers
                    WHERE question_id = %s
                    ORDER BY display_order
                """, (question['question_id'],))
                question['answers'] = cursor.fetchall()
            
            quiz['questions'] = questions
            return dict(quiz)
    
    @staticmethod
    def get_by_user(user_id):
        """Get all quizzes for a user."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT course_id, course_name, created_at
                FROM course
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (user_id,))
            return cursor.fetchall()
    
    @staticmethod
    def delete(course_id, user_id):
        """Delete a quiz (only if owned by user)."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM course
                WHERE course_id = %s AND user_id = %s
            """, (course_id, user_id))
            return cursor.rowcount > 0

from models.database import db
from datetime import datetime

class Response:
    @staticmethod
    def create(user_id, class_id, question_id, answer_id, latency_ms, points_awarded):
        """Record a student's answer."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO students_answers (user_id, class_id, question_id, answer_id, latency_ms, points_awarded)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (class_id, user_id, question_id) DO UPDATE 
                SET answer_id = EXCLUDED.answer_id, 
                    answered_at = EXCLUDED.answered_at,
                    latency_ms = EXCLUDED.latency_ms,
                    points_awarded = EXCLUDED.points_awarded
                RETURNING student_answer_id
            """, (user_id, class_id, question_id, answer_id, latency_ms, points_awarded))
            result = cursor.fetchone()
            return result['student_answer_id'] if result else None
    
    @staticmethod
    def get_by_session(class_id):
        """Get all responses for a session."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT sa.student_answer_id, sa.user_id, sa.class_id, sa.question_id,
                       sa.answer_id, sa.answered_at, sa.latency_ms, sa.points_awarded,
                       a.is_correct, a.answer_content,
                       u.user_fname, u.user_lname
                FROM students_answers sa
                JOIN answers a ON a.answer_id = sa.answer_id
                JOIN app_user u ON u.user_id = sa.user_id
                WHERE sa.class_id = %s
                ORDER BY sa.answered_at
            """, (class_id,))
            return cursor.fetchall()
    
    @staticmethod
    def get_by_question(class_id, question_id):
        """Get all responses for a specific question in a session."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT sa.student_answer_id, sa.user_id, sa.answer_id, sa.answered_at,
                       sa.latency_ms, sa.points_awarded,
                       a.is_correct, a.answer_content,
                       u.user_fname, u.user_lname,
                       cp.nickname
                FROM students_answers sa
                JOIN answers a ON a.answer_id = sa.answer_id
                JOIN app_user u ON u.user_id = sa.user_id
                LEFT JOIN class_participant cp ON cp.user_id = sa.user_id AND cp.class_id = sa.class_id
                WHERE sa.class_id = %s AND sa.question_id = %s
                ORDER BY sa.answered_at
            """, (class_id, question_id))
            return cursor.fetchall()
    
    @staticmethod
    def get_user_response(class_id, user_id, question_id):
        """Get a specific user's response to a question."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT sa.student_answer_id, sa.answer_id, sa.answered_at,
                       sa.latency_ms, sa.points_awarded,
                       a.is_correct
                FROM students_answers sa
                JOIN answers a ON a.answer_id = sa.answer_id
                WHERE sa.class_id = %s AND sa.user_id = %s AND sa.question_id = %s
            """, (class_id, user_id, question_id))
            return cursor.fetchone()
    
    @staticmethod
    def has_answered(class_id, user_id, question_id):
        """Check if user has already answered a question."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT 1 FROM students_answers
                WHERE class_id = %s AND user_id = %s AND question_id = %s
            """, (class_id, user_id, question_id))
            return cursor.fetchone() is not None
    
    @staticmethod
    def get_question_stats(class_id, question_id):
        """Get statistics for a question."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_responses,
                    SUM(CASE WHEN a.is_correct THEN 1 ELSE 0 END) as correct_count,
                    AVG(sa.latency_ms) as avg_latency
                FROM students_answers sa
                JOIN answers a ON a.answer_id = sa.answer_id
                WHERE sa.class_id = %s AND sa.question_id = %s
            """, (class_id, question_id))
            return cursor.fetchone()

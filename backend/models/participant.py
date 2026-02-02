from models.database import db

class Participant:
    @staticmethod
    def create(class_id, user_id, nickname=None):
        """Add a participant to a session."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO class_participant (class_id, user_id, nickname)
                VALUES (%s, %s, %s)
                ON CONFLICT (class_id, user_id) DO UPDATE SET nickname = EXCLUDED.nickname
                RETURNING class_participant_id
            """, (class_id, user_id, nickname))
            result = cursor.fetchone()
            return result['class_participant_id'] if result else None
    
    @staticmethod
    def get_by_id(participant_id):
        """Get participant by ID."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    cp.class_participant_id as id,
                    cp.class_id,
                    cp.user_id,
                    cp.nickname as name,
                    cp.joined_at,
                    cp.is_kicked
                FROM class_participant cp
                JOIN app_user u ON u.user_id = cp.user_id
                WHERE cp.class_participant_id = %s
            """, (participant_id,))
            return cursor.fetchone()

    @staticmethod
    def get_by_session_and_user(class_id, user_id):
        """Get participant by session and user ID."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    cp.class_participant_id as id,
                    cp.class_id,
                    cp.user_id,
                    cp.nickname as name,
                    cp.joined_at,
                    cp.is_kicked
                FROM class_participant cp
                JOIN app_user u ON u.user_id = cp.user_id 
                WHERE cp.class_id = %s AND cp.user_id = %s AND cp.is_kicked = FALSE
            """, (class_id, user_id))
            return cursor.fetchone()  # Changed from fetchall() to fetchone()

    @staticmethod
    def get_by_session(class_id):
        """Get all participants in a session."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    cp.class_participant_id as id,
                    cp.class_id,
                    cp.user_id,
                    cp.nickname as name,
                    cp.joined_at,
                    cp.is_kicked
                FROM class_participant cp
                JOIN app_user u ON u.user_id = cp.user_id
                WHERE cp.class_id = %s AND cp.is_kicked = FALSE
                ORDER BY cp.joined_at
            """, (class_id,))
            return cursor.fetchall()
    @staticmethod
    def kick(participant_id):
        """Kick a participant from the session."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                UPDATE class_participant
                SET is_kicked = TRUE
                WHERE class_participant_id = %s
            """, (participant_id,))
            return cursor.rowcount > 0
    
    @staticmethod
    def get_count(class_id):
        """Get participant count for a session."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM class_participant
                WHERE class_id = %s AND is_kicked = FALSE
            """, (class_id,))
            result = cursor.fetchone()
            return result['count'] if result else 0

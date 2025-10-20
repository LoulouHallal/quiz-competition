from models.database import db
from models.response import Response

class ScoringService:
    @staticmethod
    def calculate_points(is_correct, base_points=100, latency_ms=None, time_limit_seconds=None):
        """Calculate points for an answer."""
        if not is_correct:
            return 0
        
        # MVP: Simple scoring - correct = 1 point
        # Can be enhanced with speed bonuses later
        return 1
    
    @staticmethod
    def get_leaderboard(class_id):
        """Get leaderboard for a session."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    sa.user_id,
                    COALESCE(cp.nickname, u.user_fname || ' ' || u.user_lname) as display_name,
                    SUM(sa.points_awarded) as total_points,
                    SUM(sa.latency_ms) as total_latency,
                    COUNT(*) as questions_answered,
                    SUM(CASE WHEN a.is_correct THEN 1 ELSE 0 END) as correct_count
                FROM students_answers sa
                JOIN app_user u ON u.user_id = sa.user_id
                JOIN answers a ON a.answer_id = sa.answer_id
                LEFT JOIN class_participant cp ON cp.user_id = sa.user_id AND cp.class_id = sa.class_id
                WHERE sa.class_id = %s
                GROUP BY sa.user_id, display_name
                ORDER BY total_points DESC, total_latency ASC
            """, (class_id,))
            results = cursor.fetchall()
            
            # Add rank
            leaderboard = []
            for idx, row in enumerate(results, 1):
                leaderboard.append({
                    'rank': idx,
                    'userId': row['user_id'],
                    'name': row['display_name'],
                    'points': row['total_points'],
                    'latency': row['total_latency'],
                    'questionsAnswered': row['questions_answered'],
                    'correctCount': row['correct_count']
                })
            
            return leaderboard
    
    @staticmethod
    def get_session_summary(class_id):
        """Get complete session summary with per-question stats."""
        with db.get_cursor() as cursor:
            # Get session info
            cursor.execute("""
                SELECT cs.class_id, cs.class_name, cs.class_code, cs.status,
                       cs.started_at, cs.ended_at, c.course_name
                FROM class_session cs
                JOIN course c ON c.course_id = cs.course_id
                WHERE cs.class_id = %s
            """, (class_id,))
            session = cursor.fetchone()
            
            if not session:
                return None
            
            # Get leaderboard
            leaderboard = ScoringService.get_leaderboard(class_id)
            
            # Get per-question stats
            cursor.execute("""
                SELECT 
                    q.question_id,
                    q.question_content,
                    cq.display_order,
                    COUNT(sa.student_answer_id) as total_responses,
                    SUM(CASE WHEN a.is_correct THEN 1 ELSE 0 END) as correct_responses,
                    AVG(sa.latency_ms) as avg_latency
                FROM class_question cq
                JOIN question q ON q.question_id = cq.question_id
                LEFT JOIN students_answers sa ON sa.question_id = q.question_id AND sa.class_id = cq.class_id
                LEFT JOIN answers a ON a.answer_id = sa.answer_id
                WHERE cq.class_id = %s
                GROUP BY q.question_id, q.question_content, cq.display_order
                ORDER BY cq.display_order
            """, (class_id,))
            question_stats = cursor.fetchall()
            
            # Get participant count
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM class_participant
                WHERE class_id = %s AND is_kicked = FALSE
            """, (class_id,))
            participant_count = cursor.fetchone()['count']
            
            return {
                'session': dict(session),
                'leaderboard': leaderboard,
                'questionStats': [dict(q) for q in question_stats],
                'participantCount': participant_count
            }
    
    @staticmethod
    def export_to_csv(class_id):
        """Generate CSV data for session results."""
        summary = ScoringService.get_session_summary(class_id)
        if not summary:
            return None
        
        # CSV header
        csv_lines = ['Rank,Name,Total Points,Correct Answers,Total Latency (ms),Questions Answered']
        
        # Add leaderboard data
        for entry in summary['leaderboard']:
            csv_lines.append(
                f"{entry['rank']},{entry['name']},{entry['points']},"
                f"{entry['correctCount']},{entry['latency']},{entry['questionsAnswered']}"
            )
        
        return '\n'.join(csv_lines)

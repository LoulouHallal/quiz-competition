from models.database import db

class Question:
    @staticmethod
    def create(course_id, question_content, questiontype_id, points, time_limit_seconds, options, correct_indices):
        """Create a question with answers."""
        with db.get_cursor() as cursor:
            # Insert question
            cursor.execute("""
                INSERT INTO question (question_content, course_id, questiontype_id, points, time_limit_seconds)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING question_id
            """, (question_content, course_id, questiontype_id, points, time_limit_seconds))
            result = cursor.fetchone()
            question_id = result['question_id']
            
            # Insert answers
            for idx, option in enumerate(options):
                is_correct = idx in correct_indices
                cursor.execute("""
                    INSERT INTO answers (answer_content, question_id, is_correct, display_order)
                    VALUES (%s, %s, %s, %s)
                """, (option, question_id, is_correct, idx))
            
            return question_id
    
    @staticmethod
    def get_by_id(question_id):
        """Get question with answers."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT q.question_id, q.question_content, q.course_id, q.questiontype_id,
                       q.points, q.time_limit_seconds, q.created_at
                FROM question q
                WHERE q.question_id = %s
            """, (question_id,))
            question = cursor.fetchone()
            
            if not question:
                return None
            
            cursor.execute("""
                SELECT answer_id, answer_content, is_correct, display_order
                FROM answers
                WHERE question_id = %s
                ORDER BY display_order
            """, (question_id,))
            question['answers'] = cursor.fetchall()
            
            return dict(question)
    
    @staticmethod
    def update(question_id, question_content=None, points=None, time_limit_seconds=None, options=None, correct_indices=None):
        """Update a question."""
        with db.get_cursor() as cursor:
            if question_content or points is not None or time_limit_seconds is not None:
                updates = []
                params = []
                if question_content:
                    updates.append("question_content = %s")
                    params.append(question_content)
                if points is not None:
                    updates.append("points = %s")
                    params.append(points)
                if time_limit_seconds is not None:
                    updates.append("time_limit_seconds = %s")
                    params.append(time_limit_seconds)
                
                params.append(question_id)
                cursor.execute(f"""
                    UPDATE question
                    SET {', '.join(updates)}
                    WHERE question_id = %s
                """, params)
            
            # Update answers if provided
            if options and correct_indices is not None:
                # Delete old answers
                cursor.execute("DELETE FROM answers WHERE question_id = %s", (question_id,))
                
                # Insert new answers
                for idx, option in enumerate(options):
                    is_correct = idx in correct_indices
                    cursor.execute("""
                        INSERT INTO answers (answer_content, question_id, is_correct, display_order)
                        VALUES (%s, %s, %s, %s)
                    """, (option, question_id, is_correct, idx))
            
            return True
    
    @staticmethod
    def delete(question_id):
        """Delete a question."""
        with db.get_cursor() as cursor:
            cursor.execute("DELETE FROM question WHERE question_id = %s", (question_id,))
            return cursor.rowcount > 0
    
    @staticmethod
    def get_by_course(course_id):
        """Get all questions for a course."""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT q.question_id, q.question_content, q.questiontype_id,
                       q.points, q.time_limit_seconds, q.created_at
                FROM question q
                WHERE q.course_id = %s
                ORDER BY q.question_id
            """, (course_id,))
            questions = cursor.fetchall()
            
            for question in questions:
                cursor.execute("""
                    SELECT answer_id, answer_content, is_correct, display_order
                    FROM answers
                    WHERE question_id = %s
                    ORDER BY display_order
                """, (question['question_id'],))
                question['answers'] = cursor.fetchall()
            
            return questions

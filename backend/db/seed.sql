-- Seed data for Quiz Competition

-- Insert user roles
INSERT INTO user_role (userrole_name) VALUES 
    ('student'),
    ('teacher'),
    ('admin')
ON CONFLICT (userrole_name) DO NOTHING;

-- Insert question types
INSERT INTO question_type (questiontype_name) VALUES 
    ('mcq_single'),
    ('mcq_multi'),
    ('true_false')
ON CONFLICT (questiontype_name) DO NOTHING;

-- Insert a demo teacher (password should be hashed in production)
INSERT INTO app_user (user_fname, user_lname, user_email, user_phone, userrole_id)
VALUES ('Demo', 'Teacher', 'teacher@demo.com', NULL, 2)
ON CONFLICT (user_email) DO NOTHING;

-- Get the teacher ID
DO $$
DECLARE
    teacher_id BIGINT;
    demo_course_id BIGINT;
    q1_id BIGINT;
    q2_id BIGINT;
    q3_id BIGINT;
    q4_id BIGINT;
    q5_id BIGINT;
BEGIN
    SELECT user_id INTO teacher_id FROM app_user WHERE user_email = 'teacher@demo.com';
    
    -- Create a demo course
    INSERT INTO course (course_name, user_id)
    VALUES ('Demo Quiz - General Knowledge', teacher_id)
    RETURNING course_id INTO demo_course_id;
    
    -- Question 1
    INSERT INTO question (question_content, course_id, questiontype_id, points, time_limit_seconds)
    VALUES ('What is the capital of France?', demo_course_id, 1, 100, 30)
    RETURNING question_id INTO q1_id;
    
    INSERT INTO answers (answer_content, question_id, is_correct, display_order) VALUES
        ('London', q1_id, FALSE, 0),
        ('Paris', q1_id, TRUE, 1),
        ('Berlin', q1_id, FALSE, 2),
        ('Madrid', q1_id, FALSE, 3);
    
    -- Question 2
    INSERT INTO question (question_content, course_id, questiontype_id, points, time_limit_seconds)
    VALUES ('Which planet is known as the Red Planet?', demo_course_id, 1, 100, 30)
    RETURNING question_id INTO q2_id;
    
    INSERT INTO answers (answer_content, question_id, is_correct, display_order) VALUES
        ('Venus', q2_id, FALSE, 0),
        ('Mars', q2_id, TRUE, 1),
        ('Jupiter', q2_id, FALSE, 2),
        ('Saturn', q2_id, FALSE, 3);
    
    -- Question 3
    INSERT INTO question (question_content, course_id, questiontype_id, points, time_limit_seconds)
    VALUES ('What is 15 × 8?', demo_course_id, 1, 100, 20)
    RETURNING question_id INTO q3_id;
    
    INSERT INTO answers (answer_content, question_id, is_correct, display_order) VALUES
        ('110', q3_id, FALSE, 0),
        ('120', q3_id, TRUE, 1),
        ('130', q3_id, FALSE, 2),
        ('140', q3_id, FALSE, 3);
    
    -- Question 4
    INSERT INTO question (question_content, course_id, questiontype_id, points, time_limit_seconds)
    VALUES ('Who wrote "Romeo and Juliet"?', demo_course_id, 1, 100, 30)
    RETURNING question_id INTO q4_id;
    
    INSERT INTO answers (answer_content, question_id, is_correct, display_order) VALUES
        ('Charles Dickens', q4_id, FALSE, 0),
        ('William Shakespeare', q4_id, TRUE, 1),
        ('Jane Austen', q4_id, FALSE, 2),
        ('Mark Twain', q4_id, FALSE, 3);
    
    -- Question 5
    INSERT INTO question (question_content, course_id, questiontype_id, points, time_limit_seconds)
    VALUES ('What is the largest ocean on Earth?', demo_course_id, 1, 100, 30)
    RETURNING question_id INTO q5_id;
    
    INSERT INTO answers (answer_content, question_id, is_correct, display_order) VALUES
        ('Atlantic Ocean', q5_id, FALSE, 0),
        ('Indian Ocean', q5_id, FALSE, 1),
        ('Pacific Ocean', q5_id, TRUE, 2),
        ('Arctic Ocean', q5_id, FALSE, 3);
    
END $$;

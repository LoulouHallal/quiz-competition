-- Optional but recommended for case-insensitive unique emails
CREATE EXTENSION IF NOT EXISTS citext;

-- 1) Roles and users
CREATE TABLE user_role (
  user_role_id   SMALLSERIAL PRIMARY KEY,
  userrole_name  VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE app_user (
  user_id     BIGSERIAL PRIMARY KEY,
  user_fname  VARCHAR(100) NOT NULL,
  user_lname  VARCHAR(100) NOT NULL,
  user_email  CITEXT NOT NULL UNIQUE,
  user_phone  VARCHAR(30),
  userrole_id SMALLINT NOT NULL REFERENCES user_role(user_role_id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2) Courses (PowerPoint decks owned by a teacher)
CREATE TABLE course (
  course_id    BIGSERIAL PRIMARY KEY,
  course_name  VARCHAR(255) NOT NULL,
  user_id      BIGINT NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3) Live competition "class" (session)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'class_status') THEN
    CREATE TYPE class_status AS ENUM ('lobby','active','ended','archived');
  END IF;
END $$;

CREATE TABLE class_session (
  class_id       BIGSERIAL PRIMARY KEY,
  class_name     VARCHAR(255) NOT NULL,
  class_link     TEXT,
  class_code     VARCHAR(10) NOT NULL,     -- join code shown with QR
  course_id      BIGINT NOT NULL REFERENCES course(course_id) ON DELETE CASCADE,
  status         class_status NOT NULL DEFAULT 'lobby',
  started_at     TIMESTAMPTZ,
  ended_at       TIMESTAMPTZ,
  current_question_index INTEGER DEFAULT 0,
  settings       JSONB NOT NULL DEFAULT '{}'::jsonb, -- e.g., { "timeLimit":20, "points":100 }
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (class_code)
);

-- 4) Questions & types
CREATE TABLE question_type (
  questiontype_id   SMALLSERIAL PRIMARY KEY,
  questiontype_name VARCHAR(50) NOT NULL UNIQUE  -- e.g., 'mcq_single','mcq_multi','true_false'
);

CREATE TABLE question (
  question_id       BIGSERIAL PRIMARY KEY,
  question_content  TEXT NOT NULL,
  course_id         BIGINT NOT NULL REFERENCES course(course_id) ON DELETE CASCADE,
  questiontype_id   SMALLINT NOT NULL REFERENCES question_type(questiontype_id),
  points            INTEGER NOT NULL DEFAULT 100,     -- base score for correct answer
  time_limit_seconds INTEGER,                         -- optional per-question timer
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5) Answer options
CREATE TABLE answers (
  answer_id      BIGSERIAL PRIMARY KEY,
  answer_content TEXT NOT NULL,
  question_id    BIGINT NOT NULL REFERENCES question(question_id) ON DELETE CASCADE,
  is_correct     BOOLEAN NOT NULL DEFAULT FALSE,
  display_order  SMALLINT
);
CREATE INDEX idx_answers_question ON answers(question_id);

-- 6) Map questions into a session (order & lock)
CREATE TABLE class_question (
  class_question_id BIGSERIAL PRIMARY KEY,
  class_id    BIGINT NOT NULL REFERENCES class_session(class_id) ON DELETE CASCADE,
  question_id BIGINT NOT NULL REFERENCES question(question_id) ON DELETE CASCADE,
  display_order INTEGER NOT NULL,
  is_active   BOOLEAN NOT NULL DEFAULT FALSE,   -- current live question
  locked_at   TIMESTAMPTZ,                      -- when teacher clicked "Done"
  UNIQUE (class_id, question_id),
  UNIQUE (class_id, display_order)
);

-- 7) Participants in a session
CREATE TABLE class_participant (
  class_participant_id BIGSERIAL PRIMARY KEY,
  class_id   BIGINT NOT NULL REFERENCES class_session(class_id) ON DELETE CASCADE,
  user_id    BIGINT NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
  nickname   VARCHAR(100),                      -- allow fun names if desired
  joined_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_kicked  BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (class_id, user_id)
);

-- 8) Student answers (one per question per session per user)
CREATE TABLE students_answers (
  student_answer_id BIGSERIAL PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES app_user(user_id) ON DELETE CASCADE,
  class_id    BIGINT NOT NULL REFERENCES class_session(class_id) ON DELETE CASCADE,
  question_id BIGINT NOT NULL REFERENCES question(question_id) ON DELETE CASCADE,
  answer_id   BIGINT NOT NULL REFERENCES answers(answer_id) ON DELETE CASCADE,
  answered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  latency_ms  INTEGER,                          -- for speed-based tiebreakers
  points_awarded INTEGER NOT NULL DEFAULT 0,    -- final points after rules
  CONSTRAINT uq_one_answer UNIQUE (class_id, user_id, question_id)
);
CREATE INDEX idx_sa_class ON students_answers(class_id);
CREATE INDEX idx_sa_user ON students_answers(user_id);
CREATE INDEX idx_sa_question ON students_answers(question_id);
CREATE INDEX idx_sa_answer ON students_answers(answer_id);

-- Helpful views (optional, but handy)

-- Live leaderboard per session
CREATE OR REPLACE VIEW v_class_leaderboard AS
SELECT
  sa.class_id,
  sa.user_id,
  u.user_fname,
  u.user_lname,
  SUM(sa.points_awarded) AS score,
  COUNT(*) FILTER (WHERE a.is_correct) AS correct_count
FROM students_answers sa
JOIN answers a ON a.answer_id = sa.answer_id
JOIN app_user u ON u.user_id = sa.user_id
GROUP BY sa.class_id, sa.user_id, u.user_fname, u.user_lname;

-- Per-question summary for the teacher table
CREATE OR REPLACE VIEW v_question_summary AS
SELECT
  sa.class_id,
  sa.question_id,
  q.question_content,
  COUNT(sa.student_answer_id) AS responses,
  SUM(CASE WHEN a.is_correct THEN 1 ELSE 0 END) AS correct_responses
FROM students_answers sa
JOIN answers a ON a.answer_id = sa.answer_id
JOIN question q ON q.question_id = sa.question_id
GROUP BY sa.class_id, sa.question_id, q.question_content;

PRAGMA foreign_keys = ON;

-- Demo schema for Adaptive Learning System
-- IDs are TEXT (stable slugs), timestamps are ISO-8601 TEXT.

-- ---------- Topic ----------
CREATE TABLE IF NOT EXISTS topics (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  cluster TEXT NOT NULL,
  grade_level INTEGER NOT NULL,
  order_index INTEGER NOT NULL,
  difficulty_prior REAL NOT NULL CHECK (difficulty_prior BETWEEN 0.0 AND 1.0),
  tags_json TEXT NOT NULL DEFAULT '[]' -- JSON array of strings
);

-- ---------- TopicEdge ----------
CREATE TABLE IF NOT EXISTS topic_edges (
  id TEXT PRIMARY KEY,
  from_topic_id TEXT NOT NULL,
  to_topic_id TEXT NOT NULL,
  edge_type TEXT NOT NULL CHECK (edge_type IN ('prerequisite', 'encompassing')),
  weight REAL NOT NULL DEFAULT 0.5 CHECK (weight BETWEEN 0.0 AND 1.0),
  FOREIGN KEY (from_topic_id) REFERENCES topics(id) ON DELETE CASCADE,
  FOREIGN KEY (to_topic_id) REFERENCES topics(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_topic_edges_from ON topic_edges(from_topic_id);
CREATE INDEX IF NOT EXISTS idx_topic_edges_to ON topic_edges(to_topic_id);
CREATE INDEX IF NOT EXISTS idx_topic_edges_type ON topic_edges(edge_type);

-- ---------- Question ----------
CREATE TABLE IF NOT EXISTS questions (
  id TEXT PRIMARY KEY,
  prompt TEXT NOT NULL,
  question_type TEXT NOT NULL, -- e.g. 'mcq', 'short'
  choices_json TEXT NOT NULL DEFAULT '[]', -- JSON array, empty if not MCQ
  correct_answer TEXT NOT NULL,

  primary_topic_id TEXT NOT NULL,
  secondary_topic_ids_json TEXT NOT NULL DEFAULT '[]', -- JSON array of topic ids

  difficulty_prior REAL NOT NULL CHECK (difficulty_prior BETWEEN 0.0 AND 1.0),
  conceptual_load REAL NOT NULL CHECK (conceptual_load BETWEEN 0.0 AND 1.0),
  procedural_load REAL NOT NULL CHECK (procedural_load BETWEEN 0.0 AND 1.0),
  transfer_load REAL NOT NULL CHECK (transfer_load BETWEEN 0.0 AND 1.0),
  diagnostic_value REAL NOT NULL CHECK (diagnostic_value BETWEEN 0.0 AND 1.0),

  tags_json TEXT NOT NULL DEFAULT '[]',

  FOREIGN KEY (primary_topic_id) REFERENCES topics(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_questions_primary_topic ON questions(primary_topic_id);

-- ---------- Student ----------
CREATE TABLE IF NOT EXISTS students (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  created_at TEXT NOT NULL
);

-- ---------- Attempt ----------
CREATE TABLE IF NOT EXISTS attempts (
  id TEXT PRIMARY KEY,
  student_id TEXT NOT NULL,
  question_id TEXT NOT NULL,
  topic_id TEXT NOT NULL, -- denormalized: topic scored against

  correctness INTEGER NOT NULL CHECK (correctness IN (0,1)),
  time_taken_seconds INTEGER NOT NULL CHECK (time_taken_seconds >= 0),
  hints_used INTEGER NOT NULL CHECK (hints_used >= 0),
  confidence_rating INTEGER NOT NULL CHECK (confidence_rating BETWEEN 1 AND 5),
  self_report_reason TEXT NULL,
  submitted_at TEXT NOT NULL,

  FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
  FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_attempts_student ON attempts(student_id);
CREATE INDEX IF NOT EXISTS idx_attempts_question ON attempts(question_id);
CREATE INDEX IF NOT EXISTS idx_attempts_topic ON attempts(topic_id);
CREATE INDEX IF NOT EXISTS idx_attempts_submitted_at ON attempts(submitted_at);

-- ---------- StudentTopicState ----------
CREATE TABLE IF NOT EXISTS student_topic_state (
  student_id TEXT NOT NULL,
  topic_id TEXT NOT NULL,

  mastery_score REAL NOT NULL CHECK (mastery_score BETWEEN 0.0 AND 1.0),
  fragility_score REAL NOT NULL CHECK (fragility_score BETWEEN 0.0 AND 1.0),
  fluency_score REAL NOT NULL CHECK (fluency_score BETWEEN 0.0 AND 1.0),
  evidence_count INTEGER NOT NULL CHECK (evidence_count >= 0),
  last_updated_at TEXT NOT NULL,

  PRIMARY KEY (student_id, topic_id),
  FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
  FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_state_topic ON student_topic_state(topic_id);


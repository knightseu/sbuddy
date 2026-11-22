import { Pool } from 'pg';
import { createClient } from 'redis';
import dotenv from 'dotenv';

dotenv.config();

export const db = new Pool({
  connectionString: process.env.DATABASE_URL,
  // Opt-in: the bundled docker-compose Postgres does not serve TLS; set DATABASE_SSL=true for a managed DB
  ssl: process.env.DATABASE_SSL === 'true' ? { rejectUnauthorized: false } : false
});

export const redis = createClient({
  url: process.env.REDIS_URL,
  socket: {
    reconnectStrategy: false // Disable reconnection for development
  }
});

// Only log Redis errors once
let redisErrorLogged = false;
redis.on('error', (err) => {
  if (!redisErrorLogged) {
    console.warn('⚠️  Redis connection unavailable (optional for development)');
    redisErrorLogged = true;
  }
});

export const initializeDatabase = async () => {
  try {
    // Try to connect to Redis (optional for development)
    try {
      await redis.connect();
      console.log('✅ Connected to Redis');
    } catch (redisError) {
      console.warn('⚠️  Redis connection failed (optional for development)');
    }

    // Check the connection, and release the client so db.end() can finish (#22)
    await db.query('SELECT 1');
    console.log('✅ Connected to PostgreSQL');

    await createTables();
    console.log('✅ Database tables created/verified');
  } catch (error) {
    console.error('❌ Database initialization error:', error);
    throw error;
  }
};

const createTables = async () => {
  const queries = [
    `CREATE EXTENSION IF NOT EXISTS "uuid-ossp";`,

    `CREATE TABLE IF NOT EXISTS tenants (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      name VARCHAR(255) NOT NULL,
      subscription_tier VARCHAR(50) DEFAULT 'free',
      stripe_customer_id VARCHAR(255),
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`,

    `CREATE TABLE IF NOT EXISTS users (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      email VARCHAR(255) UNIQUE NOT NULL,
      password_hash VARCHAR(255),
      subscription_tier VARCHAR(50) DEFAULT 'free',
      tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
      email_verified BOOLEAN DEFAULT FALSE,
      oauth_provider VARCHAR(50),
      oauth_id VARCHAR(255),
      role VARCHAR(50) DEFAULT 'user',
      two_factor_secret VARCHAR(255),
      two_factor_enabled BOOLEAN DEFAULT FALSE,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`,

    `CREATE TABLE IF NOT EXISTS problems (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      title VARCHAR(500) NOT NULL,
      content TEXT NOT NULL,
      source VARCHAR(255) NOT NULL,
      category VARCHAR(100) NOT NULL,
      difficulty VARCHAR(50) DEFAULT 'medium',
      subject VARCHAR(100) NOT NULL,
      exam_type VARCHAR(100),
      exam_year INTEGER,
      problem_number INTEGER,
      tags TEXT[],
      solution TEXT,
      tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`,

    `CREATE TABLE IF NOT EXISTS user_progress (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID REFERENCES users(id) ON DELETE CASCADE,
      problem_id UUID REFERENCES problems(id) ON DELETE CASCADE,
      attempts INTEGER DEFAULT 0,
      correct_attempts INTEGER DEFAULT 0,
      last_reviewed_at TIMESTAMP,
      next_review_at TIMESTAMP,
      difficulty_rating DECIMAL(3,2) DEFAULT 2.5,
      mastery_level VARCHAR(50) DEFAULT 'learning',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(user_id, problem_id)
    );`,

    `CREATE TABLE IF NOT EXISTS study_sessions (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID REFERENCES users(id) ON DELETE CASCADE,
      problems UUID[],
      session_type VARCHAR(50) DEFAULT 'practice',
      score DECIMAL(5,2),
      completed_at TIMESTAMP,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`,

    `CREATE TABLE IF NOT EXISTS spaced_repetition_cards (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID REFERENCES users(id) ON DELETE CASCADE,
      problem_id UUID REFERENCES problems(id) ON DELETE CASCADE,
      interval INTEGER DEFAULT 1,
      repetitions INTEGER DEFAULT 0,
      easiness DECIMAL(3,2) DEFAULT 2.5,
      next_review TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(user_id, problem_id)
    );`,

    `CREATE TABLE IF NOT EXISTS refresh_tokens (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID REFERENCES users(id) ON DELETE CASCADE,
      token VARCHAR(500) UNIQUE NOT NULL,
      expires_at TIMESTAMP NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`,

    `CREATE TABLE IF NOT EXISTS email_verification_tokens (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID REFERENCES users(id) ON DELETE CASCADE,
      token VARCHAR(500) UNIQUE NOT NULL,
      expires_at TIMESTAMP NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`,

    `CREATE TABLE IF NOT EXISTS password_reset_tokens (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID REFERENCES users(id) ON DELETE CASCADE,
      token VARCHAR(500) UNIQUE NOT NULL,
      expires_at TIMESTAMP NOT NULL,
      used BOOLEAN DEFAULT FALSE,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`,

    // Generic Test Viewer Tables
    `CREATE TABLE IF NOT EXISTS test_categories (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      name VARCHAR(100) UNIQUE NOT NULL,
      display_name VARCHAR(100) NOT NULL,
      description TEXT,
      icon_url TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`,

    `CREATE TABLE IF NOT EXISTS tests (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      category_id UUID REFERENCES test_categories(id) ON DELETE CASCADE,
      name VARCHAR(255) NOT NULL,
      year INTEGER,
      variant VARCHAR(50),
      problem_count INTEGER DEFAULT 0,
      source_url TEXT,
      metadata JSONB,
      crawled_at TIMESTAMP,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`,

    `CREATE TABLE IF NOT EXISTS tags (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      name VARCHAR(100) UNIQUE NOT NULL,
      category VARCHAR(50),
      description TEXT,
      color VARCHAR(7),
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`,

    `CREATE TABLE IF NOT EXISTS test_problems (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      test_id UUID REFERENCES tests(id) ON DELETE CASCADE,
      round TEXT,
      problem_number INTEGER NOT NULL,
      title VARCHAR(500),
      content TEXT NOT NULL,
      difficulty VARCHAR(20) DEFAULT 'medium',
      points INTEGER,
      time_limit INTEGER,
      metadata JSONB,
      images TEXT[],
      answer_choices_image TEXT,
      correct_answer TEXT,
      answer_unit TEXT,
      answer_alternatives TEXT[],
      explanation TEXT,
      search_vector tsvector,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT test_problems_test_round_number_key UNIQUE NULLS NOT DISTINCT (test_id, round, problem_number)
    );`,

    // Migrate databases created before Rounds (#11). Problem identity becomes
    // (Test, Round, number); round is NULL for single-Round Tests such as AMC 10.
    // Additive only: existing rows and their ids are untouched.
    `ALTER TABLE test_problems ADD COLUMN IF NOT EXISTS round TEXT;`,
    `ALTER TABLE test_problems ADD COLUMN IF NOT EXISTS answer_unit TEXT;`,
    `ALTER TABLE test_problems ADD COLUMN IF NOT EXISTS answer_alternatives TEXT[];`,
    `DO $$ BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'test_problems_test_round_number_key') THEN
        ALTER TABLE test_problems ADD CONSTRAINT test_problems_test_round_number_key
          UNIQUE NULLS NOT DISTINCT (test_id, round, problem_number);
      END IF;
    END $$;`,
    `ALTER TABLE test_problems DROP CONSTRAINT IF EXISTS test_problems_test_id_problem_number_key;`,

    `CREATE TABLE IF NOT EXISTS problem_tags (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      problem_id UUID REFERENCES test_problems(id) ON DELETE CASCADE,
      tag_id UUID REFERENCES tags(id) ON DELETE CASCADE,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(problem_id, tag_id)
    );`,

    `CREATE TABLE IF NOT EXISTS answer_choices (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      problem_id UUID REFERENCES test_problems(id) ON DELETE CASCADE,
      choice_label VARCHAR(10),
      choice_text TEXT,
      choice_order INTEGER,
      is_correct BOOLEAN DEFAULT FALSE,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`,

    `CREATE TABLE IF NOT EXISTS problem_solutions (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      problem_id UUID REFERENCES test_problems(id) ON DELETE CASCADE,
      solution_text TEXT NOT NULL,
      solution_order INTEGER,
      author VARCHAR(255),
      upvotes INTEGER DEFAULT 0,
      is_official BOOLEAN DEFAULT FALSE,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`,

    `CREATE TABLE IF NOT EXISTS related_problems (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      problem_id UUID REFERENCES test_problems(id) ON DELETE CASCADE,
      related_problem_id UUID REFERENCES test_problems(id) ON DELETE CASCADE,
      relationship_type VARCHAR(50),
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(problem_id, related_problem_id)
    );`,

    `CREATE TABLE IF NOT EXISTS study_plans (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id TEXT NOT NULL,
      name VARCHAR(255) NOT NULL DEFAULT 'My Study Plan',
      description TEXT,
      is_active BOOLEAN DEFAULT FALSE,
      target_test_date DATE,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );`,

    `CREATE TABLE IF NOT EXISTS study_plan_problems (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      study_plan_id UUID REFERENCES study_plans(id) ON DELETE CASCADE,
      problem_id UUID REFERENCES test_problems(id) ON DELETE CASCADE,
      added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      completed BOOLEAN DEFAULT FALSE,
      notes TEXT,
      UNIQUE(study_plan_id, problem_id)
    );`,

    `CREATE INDEX IF NOT EXISTS idx_problems_tenant ON problems(tenant_id);`,
    `CREATE INDEX IF NOT EXISTS idx_problems_category ON problems(category);`,
    `CREATE INDEX IF NOT EXISTS idx_problems_exam ON problems(exam_type, exam_year);`,
    `CREATE INDEX IF NOT EXISTS idx_user_progress_user ON user_progress(user_id);`,
    `CREATE INDEX IF NOT EXISTS idx_spaced_repetition_next_review ON spaced_repetition_cards(next_review);`,
    `CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);`,
    `CREATE INDEX IF NOT EXISTS idx_users_oauth ON users(oauth_provider, oauth_id);`,
    `CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);`,
    `CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token ON refresh_tokens(token);`,

    // Indexes for Generic Test Viewer
    `CREATE INDEX IF NOT EXISTS idx_tests_category ON tests(category_id);`,
    `CREATE INDEX IF NOT EXISTS idx_tests_year ON tests(year);`,
    `CREATE INDEX IF NOT EXISTS idx_test_problems_test ON test_problems(test_id);`,
    `CREATE INDEX IF NOT EXISTS idx_test_problems_difficulty ON test_problems(difficulty);`,
    `CREATE INDEX IF NOT EXISTS idx_test_problems_search ON test_problems USING gin(search_vector);`,
    `CREATE INDEX IF NOT EXISTS idx_problem_tags_problem ON problem_tags(problem_id);`,
    `CREATE INDEX IF NOT EXISTS idx_problem_tags_tag ON problem_tags(tag_id);`,
    `CREATE INDEX IF NOT EXISTS idx_answer_choices_problem ON answer_choices(problem_id);`,
    `CREATE INDEX IF NOT EXISTS idx_problem_solutions_problem ON problem_solutions(problem_id);`,
    `CREATE INDEX IF NOT EXISTS idx_related_problems_problem ON related_problems(problem_id);`,
    `CREATE INDEX IF NOT EXISTS idx_study_plans_user ON study_plans(user_id);`,
    `CREATE INDEX IF NOT EXISTS idx_study_plan_problems_plan ON study_plan_problems(study_plan_id);`,
    `CREATE INDEX IF NOT EXISTS idx_study_plan_problems_problem ON study_plan_problems(problem_id);`,
    `CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);`,
    `CREATE INDEX IF NOT EXISTS idx_tags_category ON tags(category);`,

    // Full-text search function and trigger
    `CREATE OR REPLACE FUNCTION update_problem_search_vector() RETURNS trigger AS $$
    BEGIN
      NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.content, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.explanation, '')), 'C');
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;`,

    `DROP TRIGGER IF EXISTS test_problems_search_update ON test_problems;`,

    `CREATE TRIGGER test_problems_search_update BEFORE INSERT OR UPDATE
    ON test_problems FOR EACH ROW EXECUTE FUNCTION update_problem_search_vector();`
  ];

  for (const query of queries) {
    await db.query(query);
  }
};
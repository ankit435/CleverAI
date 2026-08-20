import { pool } from './database.js';

export async function initDb() {
  const createTablesQuery = `
    CREATE TABLE IF NOT EXISTS users (
      id SERIAL PRIMARY KEY,
      name VARCHAR(255) NOT NULL,
      email VARCHAR(255) UNIQUE NOT NULL,
      password_hash VARCHAR(255),
      google_id VARCHAR(255) UNIQUE,
      avatar_url TEXT,
      plan VARCHAR(50) DEFAULT 'Free',
      is_active BOOLEAN DEFAULT TRUE,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      last_login_at TIMESTAMP WITH TIME ZONE
    );

    CREATE TABLE IF NOT EXISTS sessions (
      id VARCHAR(255) PRIMARY KEY,
      user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      token_hash VARCHAR(255) UNIQUE NOT NULL,
      user_agent TEXT,
      ip_address VARCHAR(100),
      expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
      revoked_at TIMESTAMP WITH TIME ZONE,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      last_used_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS chat_threads (
      id VARCHAR(255) PRIMARY KEY,
      user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      title VARCHAR(255) NOT NULL,
      category VARCHAR(50) DEFAULT 'favorites',
      is_archived BOOLEAN DEFAULT FALSE,
      metadata JSONB,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS messages (
      id VARCHAR(255) PRIMARY KEY,
      thread_id VARCHAR(255) NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
      sender VARCHAR(20) NOT NULL,
      text TEXT NOT NULL,
      tool_results JSONB,
      metadata JSONB,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS agent_runs (
      id VARCHAR(255) PRIMARY KEY,
      thread_id VARCHAR(255) NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
      user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      prompt TEXT NOT NULL,
      response TEXT,
      status VARCHAR(50) DEFAULT 'pending',
      model VARCHAR(100),
      provider VARCHAR(100),
      execution_time_ms INT,
      error TEXT,
      metadata JSONB,
      started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      completed_at TIMESTAMP WITH TIME ZONE
    );

    CREATE TABLE IF NOT EXISTS tool_calls (
      id VARCHAR(255) PRIMARY KEY,
      agent_run_id VARCHAR(255) NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
      tool_id VARCHAR(100) NOT NULL,
      tool_name VARCHAR(255) NOT NULL,
      status VARCHAR(50) DEFAULT 'running',
      input JSONB,
      output JSONB,
      execution_time_ms INT,
      error TEXT,
      started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      completed_at TIMESTAMP WITH TIME ZONE
    );

    CREATE TABLE IF NOT EXISTS documents (
      id VARCHAR(255) PRIMARY KEY,
      user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      thread_id VARCHAR(255) REFERENCES chat_threads(id) ON DELETE SET NULL,
      filename VARCHAR(255) NOT NULL,
      mime_type VARCHAR(255) NOT NULL,
      size_bytes INT NOT NULL,
      markdown TEXT NOT NULL,
      status VARCHAR(50) DEFAULT 'ready',
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS document_chunks (
      id VARCHAR(255) PRIMARY KEY,
      document_id VARCHAR(255) NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      ordinal INT NOT NULL,
      heading TEXT,
      content TEXT NOT NULL,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(document_id, ordinal)
    );

    CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash);
    CREATE INDEX IF NOT EXISTS idx_chat_threads_user_id ON chat_threads(user_id);
    CREATE INDEX IF NOT EXISTS idx_messages_thread_id ON messages(thread_id);
    CREATE INDEX IF NOT EXISTS idx_agent_runs_thread_id ON agent_runs(thread_id);
    CREATE INDEX IF NOT EXISTS idx_agent_runs_user_id ON agent_runs(user_id);
    CREATE INDEX IF NOT EXISTS idx_tool_calls_agent_run_id ON tool_calls(agent_run_id);
    CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
    CREATE INDEX IF NOT EXISTS idx_documents_thread_id ON documents(thread_id);
    CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
  `;

  try {
    await pool.query(createTablesQuery);
    console.log('✅ PostgreSQL Schema initialized (users, sessions, chat_threads, messages, agent_runs, tool_calls, documents).');
  } catch (err: any) {
    console.warn('PostgreSQL table creation note:', err.message);
  }
}

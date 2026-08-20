import pg from 'pg';
import dotenv from 'dotenv';

dotenv.config();

const { Pool } = pg;

// PostgreSQL Connection Pool using environment variables
export const pool = new Pool({
  connectionString: process.env.DATABASE_URL || undefined,
  host: process.env.PGHOST || process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.PGPORT || process.env.DB_PORT || '5432'),
  user: process.env.PGUSER || process.env.DB_USER || 'postgres',
  password: process.env.PGPASSWORD || process.env.DB_PASSWORD || 'postgres',
  database: process.env.PGDATABASE || process.env.DB_NAME || 'clever_db',
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

let isPgConnected = false;

// Test DB Connection
pool.connect((err, client, release) => {
  if (err) {
    console.warn('⚠️  PostgreSQL connection note:', err.message);
    console.log('ℹ️  Auth system fallback store active for local development.');
  } else {
    isPgConnected = true;
    console.log('🐘 Connected successfully to PostgreSQL Database!');
    release();
  }
});

export const query = async (text: string, params?: any[]) => {
  try {
    return await pool.query(text, params);
  } catch (error) {
    console.error('Database Query Error:', error);
    throw error;
  }
};

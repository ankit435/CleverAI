import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import crypto from 'crypto';
import { chatRouter } from './routes/chat.js';
import { authRouter } from './routes/auth.js';
import { conversationsRouter } from './routes/conversations.js';
import { documentsRouter } from './routes/documents.js';
import { initDb } from './config/initDb.js';
import { prisma } from './config/prisma.js';

dotenv.config();

export const app = express();
const PORT = process.env.PORT || 8000;
const PYTHON_SERVER_URL = process.env.PYTHON_SERVER_URL || 'http://localhost:8001';

// Initialize PostgreSQL database schema if available
initDb();

// Request ID & Structured Logging Middleware
app.use((req: Request, res: Response, next: NextFunction) => {
  const reqId = crypto.randomUUID();
  req.headers['x-request-id'] = reqId;
  res.setHeader('X-Request-ID', reqId);
  const start = Date.now();

  res.on('finish', () => {
    const duration = Date.now() - start;
    console.log(`[${new Date().toISOString()}] [${reqId.slice(0, 8)}] ${req.method} ${req.originalUrl} -> ${res.statusCode} (${duration}ms)`);
  });
  next();
});

// Middleware
app.use(cors({
  origin: '*',
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'X-Request-ID']
}));

app.use(express.json({ limit: '10mb' }));

// Health Check Endpoint (Liveness)
app.get('/api/v1/health', (_req: Request, res: Response) => {
  res.json({
    status: 'online',
    service: 'Clever AI Multi-User Backend Server',
    version: '2.0.0',
    timestamp: new Date().toISOString()
  });
});

// Readiness Check Endpoint (PostgreSQL & Python Backend connectivity)
app.get('/api/v1/ready', async (_req: Request, res: Response) => {
  let dbStatus = 'healthy';
  let pythonAgentStatus = 'healthy';

  try {
    await prisma.$queryRaw`SELECT 1`;
  } catch (err: any) {
    dbStatus = `unhealthy: ${err.message}`;
  }

  try {
    const pyRes = await fetch(`${PYTHON_SERVER_URL}/health`, { signal: AbortSignal.timeout(1500) });
    if (!pyRes.ok) pythonAgentStatus = `degraded (status ${pyRes.status})`;
  } catch {
    pythonAgentStatus = 'fallback active (simulated agent mode)';
  }

  const isReady = dbStatus === 'healthy';
  res.status(isReady ? 200 : 503).json({
    status: isReady ? 'ready' : 'not ready',
    database: dbStatus,
    pythonAgent: pythonAgentStatus,
    timestamp: new Date().toISOString()
  });
});

// Authentication Router
app.use('/api/v1/auth', authRouter);

// Conversations & Messages Router
app.use('/api/v1/conversations', conversationsRouter);

// Authenticated document conversion and storage (MarkItDown runs in the Python service)
app.use('/api/v1/documents', documentsRouter);

// Chat & Multi-Tool Agent Execution Route
app.use('/api/v1/chat', chatRouter);

// 404 Route Handler
app.use((_req: Request, res: Response) => {
  res.status(404).json({ error: 'Endpoint not found' });
});

// Global Error Handler
app.use((err: any, _req: Request, res: Response, _next: NextFunction) => {
  console.error('Unhandled server error:', err);
  res.status(500).json({ error: 'Internal Server Error' });
});

// Start Server if executed directly
if (process.env.NODE_ENV !== 'test') {
  app.listen(PORT, () => {
    console.log(`⚡ Clever AI Multi-User Backend Server is running at: http://localhost:${PORT}`);
    console.log(`➜ Auth API endpoint: http://localhost:${PORT}/api/v1/auth`);
    console.log(`➜ Conversations API endpoint: http://localhost:${PORT}/api/v1/conversations`);
    console.log(`➜ Chat API endpoint: http://localhost:${PORT}/api/v1/chat`);
  });
}

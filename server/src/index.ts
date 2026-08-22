import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import crypto from 'crypto';
import { chatRouter } from './routes/chat.js';
import { authRouter } from './routes/auth.js';
import { conversationsRouter } from './routes/conversations.js';
import { documentsRouter } from './routes/documents.js';
import { pluginsRouter } from './routes/plugins.js';
import { browserRouter } from './routes/browser.js';
import { initDb } from './config/initDb.js';
import { prisma } from './config/prisma.js';

dotenv.config();

// ---------- Rate limiter (in-memory, no extra dep needed) ----------
const _rlStore = new Map<string, { count: number; resetAt: number }>();
function makeRateLimiter(maxReqs: number, windowMs: number) {
  return (req: Request, res: Response, next: NextFunction) => {
    const ip = (req.headers['x-forwarded-for'] as string || req.socket.remoteAddress || 'unknown').split(',')[0].trim();
    const key = `${ip}:${req.path}`;
    const now = Date.now();
    const rec = _rlStore.get(key);
    if (!rec || now > rec.resetAt) {
      _rlStore.set(key, { count: 1, resetAt: now + windowMs });
      return next();
    }
    if (rec.count >= maxReqs) {
      res.setHeader('Retry-After', String(Math.ceil((rec.resetAt - now) / 1000)));
      return res.status(429).json({ error: 'Too many requests — please try again later.' });
    }
    rec.count++;
    return next();
  };
}
// Purge stale rate-limit entries every 5 minutes to prevent memory leak
setInterval(() => {
  const now = Date.now();
  for (const [k, v] of _rlStore) if (now > v.resetAt) _rlStore.delete(k);
}, 5 * 60 * 1000);
// ---------- End rate limiter ----------

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
    // Intentionally omit full URL from logs to avoid storing PII path params.
    const safeMethod = req.method.toUpperCase();
    const safePath = req.path.replace(/\/[^/]{20,}/g, '/<id>');
    console.log(`[${new Date().toISOString()}] [${reqId.slice(0, 8)}] ${safeMethod} ${safePath} -> ${res.statusCode} (${duration}ms)`);
  });
  next();
});

// Security headers on every response (no helmet dependency needed).
app.use((_req: Request, res: Response, next: NextFunction) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.setHeader('Permissions-Policy', 'geolocation=(), microphone=(), camera=()');
  res.removeHeader('X-Powered-By');
  next();
});

// CORS: explicit allowlist — never use wildcard with credentials.
const _allowedOrigins = (process.env.ALLOWED_ORIGINS || 'http://localhost:5173,http://localhost:3000')
  .split(',').map(o => o.trim()).filter(Boolean);
app.use(cors({
  origin: (origin, callback) => {
    // Allow server-to-server / same-origin (no Origin header)
    if (!origin) return callback(null, true);

    if (_allowedOrigins.includes(origin)) return callback(null, true);

    // Accept common localhost variants (127.0.0.1 vs localhost) when the port matches
    try {
      const incoming = new URL(origin);
      const incomingHost = incoming.hostname;
      const incomingPort = incoming.port || (incoming.protocol === 'https:' ? '443' : '80');

      for (const ao of _allowedOrigins) {
        try {
          const u = new URL(ao);
          const allowedHost = u.hostname;
          const allowedPort = u.port || (u.protocol === 'https:' ? '443' : '80');
          if (allowedPort === incomingPort && (allowedHost === incomingHost || (allowedHost === 'localhost' && incomingHost === '127.0.0.1') || (allowedHost === '127.0.0.1' && incomingHost === 'localhost'))) {
            return callback(null, true);
          }
        } catch {
          // ignore parse errors for env-supplied values
        }
      }
    } catch {
      // fallthrough to deny
    }

    return callback(new Error(`CORS: origin '${origin}' not permitted`));
  },
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'X-Request-ID']
}));

// Body size: 2 MB ceiling (was 10 MB — reduces DoS surface)
app.use(express.json({ limit: '2mb' }));
app.use(express.urlencoded({ extended: true, limit: '2mb' }));

// Global rate limits
app.use('/api/v1/auth', makeRateLimiter(20, 60_000));   // 20 req/min on auth
app.use('/api/v1/chat', makeRateLimiter(30, 60_000));   // 30 req/min on chat

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

// Dynamic Plugins & Tools Registry Route
app.use('/api/v1/plugins', pluginsRouter);

// Chat & Multi-Tool Agent Execution Route
app.use('/api/v1/chat', chatRouter);

// Browser AI Agent Control & Session Route
app.use('/api/v1/browser', browserRouter);

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

import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import crypto from 'crypto';
import { prisma } from '../config/prisma.js';

// Centralised JWT secret — fail fast in production rather than silently using a weak default.
const _rawSecret = process.env.JWT_SECRET || '';
if (!_rawSecret) {
  if (process.env.NODE_ENV === 'production') {
    throw new Error('JWT_SECRET environment variable must be set in production.');
  }
  console.warn('\u26a0\ufe0f  JWT_SECRET not set \u2014 using insecure dev fallback. Do NOT use in production.');
}
export const JWT_SECRET = _rawSecret || 'dev-only-insecure-jwt-secret';

export function hashToken(token: string): string {
  return crypto.createHash('sha256').update(token).digest('hex');
}

export interface AuthenticatedUser {
  id: number;
  email: string;
  name: string;
  sessionId: string;
}

export interface AuthenticatedRequest extends Request {
  user?: AuthenticatedUser;
  rawToken?: string;
}

export const authenticateToken = async (req: AuthenticatedRequest, res: Response, next: NextFunction) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];

  if (!token) {
    return res.status(401).json({ error: 'Access token required' });
  }

  try {
    const decoded = jwt.verify(token, JWT_SECRET) as { id: number; email: string; name: string };
    const tokenHash = hashToken(token);

    // Verify session in PostgreSQL database
    const session = await prisma.session.findUnique({
      where: { tokenHash },
      include: { user: true }
    });

    if (!session) {
      // If DB session does not exist (e.g. legacy token), reject to ensure security
      return res.status(401).json({ error: 'Session not found or invalid. Please log in again.' });
    }

    if (session.revokedAt) {
      return res.status(401).json({ error: 'Session has been revoked. Please log in again.' });
    }

    if (session.expiresAt < new Date()) {
      return res.status(401).json({ error: 'Session expired. Please log in again.' });
    }

    if (!session.user.isActive) {
      return res.status(403).json({ error: 'Account is deactivated. Please contact support.' });
    }

    req.user = {
      id: session.user.id,
      email: session.user.email,
      name: session.user.name,
      sessionId: session.id
    };
    req.rawToken = token;

    // Asynchronously touch session lastUsedAt
    prisma.session.update({
      where: { id: session.id },
      data: { lastUsedAt: new Date() }
    }).catch(() => {});

    next();
  } catch (err: any) {
    if (err.name === 'TokenExpiredError') {
      return res.status(401).json({ error: 'Token expired' });
    }
    return res.status(403).json({ error: 'Invalid or malformed token' });
  }
};


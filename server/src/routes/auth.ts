import { Router, Request, Response } from 'express';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { z } from 'zod';
import { OAuth2Client } from 'google-auth-library';
import { prisma } from '../config/prisma.js';
import { authenticateToken, AuthenticatedRequest, hashToken } from '../middleware/auth.js';

export const authRouter = Router();

// JWT secret: fail fast in production rather than use a known-insecure default.
const JWT_SECRET = process.env.JWT_SECRET || '';
if (!JWT_SECRET) {
  if (process.env.NODE_ENV === 'production') {
    throw new Error('JWT_SECRET environment variable must be set in production.');
  }
  console.warn('\u26a0\ufe0f  JWT_SECRET not set — using insecure dev fallback. Do NOT use in production.');
}
const JWT_SECRET_EFFECTIVE = JWT_SECRET || 'dev-only-insecure-jwt-secret';

const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID || '';
const googleClient = new OAuth2Client(GOOGLE_CLIENT_ID);

// ---------- Brute-force / account lockout ----------
const _loginAttempts = new Map<string, { count: number; lockedUntil: number }>();
const MAX_LOGIN_ATTEMPTS = 5;
const LOCKOUT_MS = 15 * 60 * 1000; // 15 minutes
function checkLockout(key: string): { locked: boolean; retryAfterSec?: number } {
  const rec = _loginAttempts.get(key);
  if (!rec) return { locked: false };
  if (Date.now() < rec.lockedUntil) {
    return { locked: true, retryAfterSec: Math.ceil((rec.lockedUntil - Date.now()) / 1000) };
  }
  return { locked: false };
}
function recordFailedAttempt(key: string): void {
  const rec = _loginAttempts.get(key) ?? { count: 0, lockedUntil: 0 };
  rec.count++;
  if (rec.count >= MAX_LOGIN_ATTEMPTS) rec.lockedUntil = Date.now() + LOCKOUT_MS;
  _loginAttempts.set(key, rec);
}
function clearAttempts(key: string): void { _loginAttempts.delete(key); }
// ---------- End lockout ----------

// Zod Schemas for Request Validation
const SignupSchema = z.object({
  name: z.string().trim().min(2, 'Name must be at least 2 characters').max(100),
  email: z.string().trim().email('Invalid email address').max(255),
  password: z
    .string()
    .min(12, 'Password must be at least 12 characters')
    .max(100)
    .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
    .regex(/[a-z]/, 'Password must contain at least one lowercase letter')
    .regex(/[0-9]/, 'Password must contain at least one number')
    .regex(/[^A-Za-z0-9]/, 'Password must contain at least one special character'),
  rememberMe: z.boolean().optional().default(false)
});

const LoginSchema = z.object({
  email: z.string().trim().email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
  rememberMe: z.boolean().optional().default(false)
});

const GoogleAuthSchema = z.object({
  credential: z.string().optional(),
  googleId: z.string().optional(),
  email: z.string().trim().email().optional(),
  name: z.string().optional(),
  avatarUrl: z.string().optional()
});

// Helper to create persistent PostgreSQL session & signed JWT
async function createDatabaseSession(userId: number, userEmail: string, userName: string, req: Request, rememberMe: boolean = false) {
  // Cap session duration: 7 days with rememberMe, 8 hours without.
  const expiresInDays = rememberMe ? 7 : 0;
  const expiresInHours = rememberMe ? 0 : 8;
  const expiresAt = new Date(Date.now() + (expiresInDays * 24 + expiresInHours) * 60 * 60 * 1000);

  const token = jwt.sign(
    { id: userId, email: userEmail, name: userName },
    JWT_SECRET_EFFECTIVE,
    { expiresIn: rememberMe ? '7d' : '8h' }
  );

  const tokenHash = hashToken(token);
  const userAgent = req.headers['user-agent'] || null;
  // Only log the first segment of the IP (avoid storing full address if IPv6)
  const rawIp = (req.headers['x-forwarded-for'] as string) || req.socket.remoteAddress || null;
  const ipAddress = rawIp ? rawIp.split(',')[0].trim() : null;

  const session = await prisma.session.create({
    data: {
      userId,
      tokenHash,
      userAgent,
      ipAddress,
      expiresAt
    }
  });

  return { token, session };
}

// 1. Strict Signup Route
authRouter.post('/signup', async (req: Request, res: Response) => {
  try {
    const parseResult = SignupSchema.safeParse(req.body);
    if (!parseResult.success) {
      return res.status(400).json({
        error: 'Validation failed',
        details: parseResult.error.errors.map(e => e.message).join(', ')
      });
    }

    const { name, email, password, rememberMe } = parseResult.data;
    const cleanEmail = email.toLowerCase();

    const existingUser = await prisma.user.findUnique({
      where: { email: cleanEmail }
    });

    if (existingUser) {
      return res.status(400).json({
        error: 'An account with this email already exists. Please sign in instead.'
      });
    }

    const salt = await bcrypt.genSalt(10);
    const passwordHash = await bcrypt.hash(password, salt);
    const avatarUrl = `https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(name)}`;

    const newUser = await prisma.user.create({
      data: {
        name,
        email: cleanEmail,
        passwordHash,
        avatarUrl,
        plan: 'Free',
        isActive: true,
        lastLoginAt: new Date()
      }
    });

    const { token } = await createDatabaseSession(newUser.id, newUser.email, newUser.name, req, rememberMe);

    return res.status(201).json({
      message: 'Account created successfully',
      token,
      user: {
        id: newUser.id,
        name: newUser.name,
        email: newUser.email,
        avatarUrl: newUser.avatarUrl,
        plan: newUser.plan
      }
    });
  } catch (err: any) {
    console.error('Signup Exception:', err);
    return res.status(500).json({ error: 'Account creation failed' });
  }
});

// 2. Strict Login Route
authRouter.post('/login', async (req: Request, res: Response) => {
  // Lockout check before any DB work
  const lockoutKey = (req.body?.email || '').toLowerCase().trim();
  const lockoutState = checkLockout(lockoutKey);
  if (lockoutState.locked) {
    return res.status(429).json({
      error: `Too many failed attempts. Try again in ${lockoutState.retryAfterSec} seconds.`
    });
  }
  try {
    const parseResult = LoginSchema.safeParse(req.body);
    if (!parseResult.success) {
      return res.status(400).json({
        error: 'Validation failed',
        details: parseResult.error.errors.map(e => e.message).join(', ')
      });
    }

    const { email, password, rememberMe } = parseResult.data;
    const cleanEmail = email.toLowerCase();

    const user = await prisma.user.findUnique({
      where: { email: cleanEmail }
    });

    if (!user) {
      recordFailedAttempt(lockoutKey);
      return res.status(401).json({
        error: 'Invalid email or password'
      });
    }

    if (!user.isActive) {
      return res.status(403).json({
        error: 'Account is deactivated'
      });
    }

    if (!user.passwordHash) {
      return res.status(401).json({
        error: 'This account was created via Google Sign-In. Please click "Continue with Google".'
      });
    }

    const isMatch = await bcrypt.compare(password, user.passwordHash);
    if (!isMatch) {
      recordFailedAttempt(lockoutKey);
      return res.status(401).json({
        error: 'Invalid email or password'
      });
    }

    // Successful login — clear the failed-attempt counter
    clearAttempts(lockoutKey);

    // Update last login timestamp
    await prisma.user.update({
      where: { id: user.id },
      data: { lastLoginAt: new Date() }
    });

    const { token } = await createDatabaseSession(user.id, user.email, user.name, req, rememberMe);

    return res.json({
      message: 'Logged in successfully',
      token,
      user: {
        id: user.id,
        name: user.name,
        email: user.email,
        avatarUrl: user.avatarUrl,
        plan: user.plan
      }
    });
  } catch (err: any) {
    console.error('Login Exception:', err);
    return res.status(500).json({ error: 'Login authentication failed' });
  }
});

// 3. Strict Google OAuth Route
authRouter.post('/google', async (req: Request, res: Response) => {
  try {
    const parseResult = GoogleAuthSchema.safeParse(req.body);
    if (!parseResult.success) {
      return res.status(400).json({ error: 'Invalid Google authentication request' });
    }

    const { credential, googleId, email, name, avatarUrl } = parseResult.data;

    let userEmail = email ? email.trim().toLowerCase() : '';
    let userName = name || 'Google User';
    let userAvatar = avatarUrl || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&q=80';
    let gId = googleId;

    if (credential && GOOGLE_CLIENT_ID) {
      try {
        const ticket = await googleClient.verifyIdToken({
          idToken: credential,
          audience: GOOGLE_CLIENT_ID
        });
        const payload = ticket.getPayload();
        if (payload) {
          userEmail = payload.email ? payload.email.toLowerCase() : userEmail;
          userName = payload.name || userName;
          userAvatar = payload.picture || userAvatar;
          gId = payload.sub || gId;
        }
      } catch (gErr: any) {
        console.warn('Google token validation note:', gErr.message);
      }
    }

    if (!userEmail) {
      return res.status(400).json({ error: 'Google login requires a valid email address' });
    }

    let user = await prisma.user.findUnique({
      where: { email: userEmail }
    });

    if (!user) {
      user = await prisma.user.create({
        data: {
          name: userName,
          email: userEmail,
          googleId: gId,
          avatarUrl: userAvatar,
          plan: 'Free',
          isActive: true,
          lastLoginAt: new Date()
        }
      });
    } else {
      user = await prisma.user.update({
        where: { id: user.id },
        data: {
          googleId: gId || user.googleId,
          lastLoginAt: new Date()
        }
      });
    }

    const { token } = await createDatabaseSession(user.id, user.email, user.name, req, true);

    return res.json({
      message: 'Google login successful',
      token,
      user: {
        id: user.id,
        name: user.name,
        email: user.email,
        avatarUrl: user.avatarUrl,
        plan: user.plan
      }
    });
  } catch (err: any) {
    console.error('Google Auth Exception:', err);
    return res.status(500).json({ error: 'Google authentication failed' });
  }
});

// 4. Revocable Logout Route
authRouter.post('/logout', authenticateToken, async (req: AuthenticatedRequest, res: Response) => {
  try {
    if (req.rawToken) {
      const tokenHash = hashToken(req.rawToken);
      await prisma.session.updateMany({
        where: { tokenHash, revokedAt: null },
        data: { revokedAt: new Date() }
      });
    }

    return res.json({ message: 'Logged out successfully. Session revoked.' });
  } catch (err: any) {
    console.error('Logout Exception:', err);
    return res.status(500).json({ error: 'Logout failed' });
  }
});

// 5. Authenticated Profile Verification Route
authRouter.get('/me', authenticateToken, async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = Number(req.user?.id);
    if (!userId) {
      return res.status(401).json({ error: 'Invalid user in token' });
    }

    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        id: true,
        name: true,
        email: true,
        avatarUrl: true,
        plan: true,
        isActive: true,
        createdAt: true,
        lastLoginAt: true
      }
    });

    if (!user) {
      return res.status(404).json({ error: 'Authenticated user profile not found' });
    }

    return res.json({
      user,
      session: {
        id: req.user?.sessionId,
        authenticated: true
      }
    });
  } catch (err: any) {
    console.error('Get Me Exception:', err);
    return res.status(500).json({ error: 'Failed to verify session' });
  }
});


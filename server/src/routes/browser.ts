import { Router, Response } from 'express';
import { z } from 'zod';
import { AuthenticatedRequest, authenticateToken } from '../middleware/auth.js';
import { prisma } from '../config/prisma.js';

export const browserRouter = Router();
const PYTHON_SERVER_URL = process.env.PYTHON_SERVER_URL || 'http://localhost:8001';
const INTERNAL_SERVICE_KEY = process.env.INTERNAL_SERVICE_KEY || 'clever-internal-agent-secret-key-prod-2026';

// All browser control routes require authentication and strict user isolation
browserRouter.use(authenticateToken);

// Validation Schemas
const connectSchema = z.object({
  mode: z.enum(['existing_cdp', 'existing_extension', 'managed_browser', 'remote_browser']).default('existing_cdp'),
  cdpUrl: z.string().url().or(z.string().regex(/^https?:\/\/.+/)).default('http://127.0.0.1:9222'),
  userDataDir: z.string().optional()
});

const selectTabSchema = z.object({
  tabId: z.string().min(1, 'tabId is required')
});

const openTabSchema = z.object({
  url: z.string().default('about:blank')
});

// Stagehand instruction-based schemas (no selectors/element IDs — Stagehand's
// AI resolves targets from plain natural-language instructions).
const navigateSchema = z.object({
  url: z.string().min(1, 'url is required')
});

const actSchema = z.object({
  instruction: z.string().min(1, 'instruction is required'),
  confirmed: z.boolean().default(false)
});

const observeSchema = z.object({
  instruction: z.string().optional()
});

const extractSchema = z.object({
  instruction: z.string().min(1, 'instruction is required')
});

const confirmSchema = z.object({
  confirmationId: z.string().min(1, 'confirmationId is required'),
  approved: z.boolean()
});

// Helper function to call Python Microservice
async function callPythonBrowserService(endpoint: string, method: string = 'POST', body?: any) {
  const res = await fetch(`${PYTHON_SERVER_URL}${endpoint}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'x-internal-service-key': INTERNAL_SERVICE_KEY
    },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(3000)
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Python service responded with status ${res.status}: ${errText}`);
  }
  return res.json();
}

// 1. POST /api/v1/browser/connect
browserRouter.post('/connect', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const parsed = connectSchema.parse(req.body);
    const userId = Number(req.user!.id);

    const pyData = await callPythonBrowserService('/api/v1/browser/connect', 'POST', {
      mode: parsed.mode,
      cdp_url: parsed.cdpUrl,
      user_data_dir: parsed.userDataDir,
      userId
    });

    // Upsert or record browser session in PostgreSQL
    if (pyData.success) {
      await prisma.browserSession.upsert({
        where: { id: `session_user_${userId}` },
        update: {
          mode: parsed.mode,
          cdpUrl: parsed.cdpUrl,
          status: 'connected',
          connectedAt: new Date(),
          lastActiveAt: new Date()
        },
        create: {
          id: `session_user_${userId}`,
          userId,
          mode: parsed.mode,
          cdpUrl: parsed.cdpUrl,
          status: 'connected',
          connectedAt: new Date()
        }
      });
    }

    res.json(pyData);
  } catch (err: any) {
    if (err instanceof z.ZodError) {
      return res.status(400).json({ error: err.errors[0]?.message || 'Validation error' });
    }
    res.status(500).json({ error: err.message || 'Failed to connect to browser' });
  }
});

// 2. POST /api/v1/browser/disconnect
browserRouter.post('/disconnect', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = Number(req.user!.id);
    const pyData = await callPythonBrowserService('/api/v1/browser/disconnect', 'POST', { userId });

    await prisma.browserSession.updateMany({
      where: { userId },
      data: { status: 'disconnected', lastActiveAt: new Date() }
    });

    res.json(pyData);
  } catch (err: any) {
    res.status(500).json({ error: err.message || 'Failed to disconnect from browser' });
  }
});

// 3. GET /api/v1/browser/status
browserRouter.get('/status', async (req: AuthenticatedRequest, res: Response) => {
  const userId = Number(req.user!.id);
  try {
    const pyData = await callPythonBrowserService(`/api/v1/browser/status?userId=${userId}`, 'GET');
    res.json({ ...pyData, userId, user_id: userId });
  } catch (err: any) {
    res.json({
      connected: false,
      mode: 'existing_cdp',
      endpoint: 'http://127.0.0.1:9222',
      tabs_count: 0,
      active_tab: null,
      tabs: [],
      userId,
      user_id: userId,
      error: err.message
    });
  }
});

// 4. GET /api/v1/browser/tabs
browserRouter.get('/tabs', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = Number(req.user!.id);
    const pyData = await callPythonBrowserService(`/api/v1/browser/tabs?userId=${userId}`, 'GET');
    res.json(pyData);
  } catch (err: any) {
    res.status(500).json({ error: err.message || 'Failed to list tabs' });
  }
});

// 5. POST /api/v1/browser/tabs/select
browserRouter.post('/tabs/select', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { tabId } = selectTabSchema.parse(req.body);
    const userId = Number(req.user!.id);

    const pyData = await callPythonBrowserService('/api/v1/browser/tabs/select', 'POST', {
      tab_id: tabId,
      userId
    });
    res.json(pyData);
  } catch (err: any) {
    if (err instanceof z.ZodError) {
      return res.status(400).json({ error: err.errors[0]?.message || 'Validation error' });
    }
    res.status(500).json({ error: err.message || 'Failed to select tab' });
  }
});

// 6. POST /api/v1/browser/tabs/open
browserRouter.post('/tabs/open', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { url } = openTabSchema.parse(req.body);
    const userId = Number(req.user!.id);

    const pyData = await callPythonBrowserService('/api/v1/browser/tabs/open', 'POST', {
      url,
      userId
    });
    res.json(pyData);
  } catch (err: any) {
    res.status(500).json({ error: err.message || 'Failed to open new tab' });
  }
});

// 7. POST /api/v1/browser/tabs/close
browserRouter.post('/tabs/close', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { tabId } = selectTabSchema.parse(req.body);
    const userId = Number(req.user!.id);

    const pyData = await callPythonBrowserService('/api/v1/browser/tabs/close', 'POST', {
      tab_id: tabId,
      userId
    });
    res.json(pyData);
  } catch (err: any) {
    res.status(500).json({ error: err.message || 'Failed to close tab' });
  }
});

// 8. POST /api/v1/browser/navigate
browserRouter.post('/navigate', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { url } = navigateSchema.parse(req.body);
    const userId = Number(req.user!.id);

    const pyData = await callPythonBrowserService('/api/v1/browser/navigate', 'POST', { url, userId });

    await prisma.browserActionAudit.create({
      data: {
        userId,
        action: 'navigate',
        targetUrl: url,
        status: pyData.status || 'success',
        durationMs: pyData.duration_ms || 0,
        error: pyData.error || null
      }
    }).catch(() => {});

    res.json(pyData);
  } catch (err: any) {
    if (err instanceof z.ZodError) {
      return res.status(400).json({ error: err.errors[0]?.message || 'Validation error' });
    }
    res.status(500).json({ error: err.message || 'Failed to navigate' });
  }
});

// 9. POST /api/v1/browser/act — Stagehand natural-language action (click/type/scroll/etc.)
browserRouter.post('/act', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { instruction, confirmed } = actSchema.parse(req.body);
    const userId = Number(req.user!.id);

    const pyData = await callPythonBrowserService('/api/v1/browser/act', 'POST', { instruction, confirmed, userId });

    // Record Action Audit Log in PostgreSQL
    await prisma.browserActionAudit.create({
      data: {
        userId,
        action: 'act',
        textInput: instruction,
        status: pyData.status || 'success',
        riskLevel: pyData.data?.risk_level || 'low',
        durationMs: pyData.duration_ms || 0,
        error: pyData.error || null
      }
    }).catch(() => {});

    res.json(pyData);
  } catch (err: any) {
    if (err instanceof z.ZodError) {
      return res.status(400).json({ error: err.errors[0]?.message || 'Validation error' });
    }
    res.status(500).json({ error: err.message || 'Failed to execute browser action' });
  }
});

// 10. POST /api/v1/browser/observe — discover actionable elements on the current page
browserRouter.post('/observe', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { instruction } = observeSchema.parse(req.body);
    const userId = Number(req.user!.id);

    const pyData = await callPythonBrowserService('/api/v1/browser/observe', 'POST', { instruction, userId });
    res.json(pyData);
  } catch (err: any) {
    if (err instanceof z.ZodError) {
      return res.status(400).json({ error: err.errors[0]?.message || 'Validation error' });
    }
    res.status(500).json({ error: err.message || 'Failed to observe page' });
  }
});

// 11. POST /api/v1/browser/extract — pull structured/free-text data from the current page
browserRouter.post('/extract', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { instruction } = extractSchema.parse(req.body);
    const userId = Number(req.user!.id);

    const pyData = await callPythonBrowserService('/api/v1/browser/extract', 'POST', { instruction, userId });
    res.json(pyData);
  } catch (err: any) {
    if (err instanceof z.ZodError) {
      return res.status(400).json({ error: err.errors[0]?.message || 'Validation error' });
    }
    res.status(500).json({ error: err.message || 'Failed to extract page data' });
  }
});

// 12. POST /api/v1/browser/confirm
browserRouter.post('/confirm', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const { confirmationId, approved } = confirmSchema.parse(req.body);
    const userId = Number(req.user!.id);

    const pyData = await callPythonBrowserService('/api/v1/browser/confirm', 'POST', {
      confirmation_id: confirmationId,
      approved,
      userId
    });
    res.json(pyData);
  } catch (err: any) {
    if (err instanceof z.ZodError) {
      return res.status(400).json({ error: err.errors[0]?.message || 'Validation error' });
    }
    res.status(500).json({ error: err.message || 'Failed to resolve confirmation' });
  }
});

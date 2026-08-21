import { Router, Response, raw } from 'express';
import { randomUUID } from 'crypto';
import { prisma } from '../config/prisma.js';
import { authenticateToken, AuthenticatedRequest } from '../middleware/auth.js';

export const documentsRouter = Router();

const PYTHON_SERVER_URL = process.env.PYTHON_SERVER_URL || 'http://127.0.0.1:8001';
const MAX_DOCUMENT_BYTES = 25 * 1024 * 1024;
const ALLOWED_EXTENSIONS = new Set(['.pdf', '.docx', '.pptx', '.xlsx', '.xls', '.csv', '.txt', '.md', '.html', '.htm', '.json', '.xml']);

function safeFilename(value: string | undefined): string | null {
  if (!value || value.length > 255 || value.includes('/') || value.includes('\\')) return null;
  const filename = value.replace(/[\x00-\x1F<>:"|?*]/g, '_');
  const dot = filename.lastIndexOf('.');
  if (dot < 1 || !ALLOWED_EXTENSIONS.has(filename.slice(dot).toLowerCase())) return null;
  return filename;
}

documentsRouter.use(authenticateToken);

// Binary uploads avoid parsing document bytes as JSON; filename and mime type travel as headers.
documentsRouter.post('/upload', raw({ type: 'application/octet-stream', limit: MAX_DOCUMENT_BYTES }), async (req: AuthenticatedRequest, res: Response) => {
  const filename = safeFilename(req.header('x-document-filename'));
  const mimeType = (req.header('x-document-mime-type') || 'application/octet-stream').slice(0, 255);
  const file = req.body as Buffer;

  if (!filename || !Buffer.isBuffer(file) || file.length === 0) {
    return res.status(400).json({ error: 'Upload a non-empty supported document with a valid filename.' });
  }
  if (file.length > MAX_DOCUMENT_BYTES) {
    return res.status(413).json({ error: 'Document exceeds the 25 MB limit.' });
  }

  try {
    const form = new FormData();
    const blob = new Blob([new Uint8Array(file)], { type: mimeType });
    form.append('file', blob, filename);

    const INTERNAL_SERVICE_KEY = process.env.INTERNAL_SERVICE_KEY || 'clever-internal-agent-secret-key-prod-2026';
    const conversion = await fetch(`${PYTHON_SERVER_URL}/api/v1/documents/convert`, {
      method: 'POST',
      body: form,
      headers: {
        'x-internal-service-key': INTERNAL_SERVICE_KEY
      },
      signal: AbortSignal.timeout(120_000)
    });
    if (!conversion.ok) {
      const body = await conversion.text();
      return res.status(422).json({ error: `Document conversion failed: ${body.slice(0, 500)}` });
    }
    const converted = await conversion.json() as { markdown: string; chunks: Array<{ ordinal: number; heading?: string; content: string }> };
    if (!converted.markdown?.trim() || !Array.isArray(converted.chunks)) {
      return res.status(422).json({ error: 'No readable text could be extracted from this document.' });
    }

    const document = await prisma.document.create({
      data: {
        id: randomUUID(), userId: Number(req.user!.id), filename, mimeType, sizeBytes: file.length,
        markdown: converted.markdown,
        chunks: { create: converted.chunks.map(chunk => ({
          id: randomUUID(), ordinal: chunk.ordinal, heading: chunk.heading || null, content: chunk.content
        })) }
      },
      select: { id: true, filename: true, sizeBytes: true, createdAt: true, _count: { select: { chunks: true } } }
    });
    return res.status(201).json({ document: { ...document, chunkCount: document._count.chunks, _count: undefined } });
  } catch (error: any) {
    console.error('Document upload error:', error);
    return res.status(503).json({ error: 'Document conversion service is unavailable.' });
  }
});

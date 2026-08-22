import { Router, Response } from 'express';
import { z } from 'zod';
import { prisma } from '../config/prisma.js';
import { authenticateToken, AuthenticatedRequest } from '../middleware/auth.js';

export const conversationsRouter = Router();

// Require authentication on all conversation routes
conversationsRouter.use(authenticateToken);

const CreateConversationSchema = z.object({
  title: z.string().trim().min(1).max(200).optional(),
  category: z.string().trim().max(50).optional().default('favorites'),
  metadata: z.record(z.any()).optional()
});

const UpdateConversationSchema = z.object({
  title: z.string().trim().min(1).max(200).optional(),
  category: z.string().trim().max(50).optional(),
  isArchived: z.boolean().optional(),
  metadata: z.record(z.any()).optional()
});

// 1. GET /api/v1/conversations - List user's conversations with pagination & filtering
conversationsRouter.get('/', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = Number(req.user!.id);
    const page = Math.max(1, parseInt(req.query.page as string) || 1);
    const limit = Math.min(100, Math.max(1, parseInt(req.query.limit as string) || 20));
    const skip = (page - 1) * limit;
    const category = req.query.category as string | undefined;
    const search = req.query.search as string | undefined;

    const whereClause: any = {
      userId,
      isArchived: false
    };

    if (category && category !== 'all') {
      whereClause.category = category;
    }

    if (search && search.trim()) {
      whereClause.title = {
        contains: search.trim(),
        mode: 'insensitive'
      };
    }

    const [total, conversations] = await Promise.all([
      prisma.chatThread.count({ where: whereClause }),
      prisma.chatThread.findMany({
        where: whereClause,
        orderBy: { updatedAt: 'desc' },
        skip,
        take: limit,
        include: {
          messages: {
            orderBy: { createdAt: 'desc' },
            take: 1,
            select: { id: true, sender: true, text: true, createdAt: true }
          },
          _count: {
            select: { messages: true, agentRuns: true }
          }
        }
      })
    ]);

    const formatted = conversations.map(c => ({
      id: c.id,
      title: c.title,
      category: c.category,
      isArchived: c.isArchived,
      metadata: c.metadata,
      createdAt: c.createdAt,
      updatedAt: c.updatedAt,
      messageCount: c._count.messages,
      agentRunCount: c._count.agentRuns,
      lastMessage: c.messages[0] || null
    }));

    return res.json({
      conversations: formatted,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit)
      }
    });
  } catch (err: any) {
    console.error('List Conversations Error:', err);
    return res.status(500).json({ error: 'Failed to fetch conversations' });
  }
});

// 2. POST /api/v1/conversations - Create a new conversation
conversationsRouter.post('/', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = Number(req.user!.id);
    const parseResult = CreateConversationSchema.safeParse(req.body);
    if (!parseResult.success) {
      return res.status(400).json({
        error: 'Validation failed',
        details: parseResult.error.errors.map(e => e.message).join(', ')
      });
    }

    const { title, category, metadata } = parseResult.data;

    const conversation = await prisma.chatThread.create({
      data: {
        userId,
        title: title || 'New Conversation',
        category: category || 'favorites',
        metadata: metadata || undefined
      }
    });

    return res.status(201).json({
      message: 'Conversation created successfully',
      conversation: {
        id: conversation.id,
        title: conversation.title,
        category: conversation.category,
        isArchived: conversation.isArchived,
        metadata: conversation.metadata,
        createdAt: conversation.createdAt,
        updatedAt: conversation.updatedAt,
        messages: []
      }
    });
  } catch (err: any) {
    console.error('Create Conversation Error:', err);
    return res.status(500).json({ error: 'Failed to create conversation' });
  }
});

// 3. GET /api/v1/conversations/:id - Get single conversation with full message history
conversationsRouter.get('/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = Number(req.user!.id);
    const conversationId = req.params.id;

    const conversation = await prisma.chatThread.findFirst({
      where: {
        id: conversationId,
        userId // Strict User Isolation
      },
      include: {
        messages: {
          orderBy: { createdAt: 'asc' }
        }
      }
    });

    if (!conversation) {
      return res.status(404).json({ error: 'Conversation not found or access denied' });
    }

    return res.json({
      conversation: {
        id: conversation.id,
        title: conversation.title,
        category: conversation.category,
        isArchived: conversation.isArchived,
        metadata: conversation.metadata,
        createdAt: conversation.createdAt,
        updatedAt: conversation.updatedAt,
        messages: conversation.messages
      }
    });
  } catch (err: any) {
    console.error('Get Conversation Error:', err);
    return res.status(500).json({ error: 'Failed to fetch conversation' });
  }
});

// 4. PATCH /api/v1/conversations/:id - Update conversation title/category
conversationsRouter.patch('/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = Number(req.user!.id);
    const conversationId = req.params.id;

    const parseResult = UpdateConversationSchema.safeParse(req.body);
    if (!parseResult.success) {
      return res.status(400).json({
        error: 'Validation failed',
        details: parseResult.error.errors.map(e => e.message).join(', ')
      });
    }

    // Verify ownership first
    const existing = await prisma.chatThread.findFirst({
      where: { id: conversationId, userId }
    });

    if (!existing) {
      return res.status(404).json({ error: 'Conversation not found or access denied' });
    }

    const updated = await prisma.chatThread.update({
      where: { id: conversationId },
      data: {
        ...parseResult.data,
        updatedAt: new Date()
      }
    });

    return res.json({
      message: 'Conversation updated successfully',
      conversation: updated
    });
  } catch (err: any) {
    console.error('Update Conversation Error:', err);
    return res.status(500).json({ error: 'Failed to update conversation' });
  }
});

// 5. DELETE /api/v1/conversations/:id - Delete conversation and its messages
conversationsRouter.delete('/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = Number(req.user!.id);
    const conversationId = req.params.id;

    const existing = await prisma.chatThread.findFirst({
      where: { id: conversationId, userId }
    });

    if (!existing) {
      return res.status(404).json({ error: 'Conversation not found or access denied' });
    }

    await prisma.chatThread.delete({
      where: { id: conversationId }
    });

    return res.json({ message: 'Conversation deleted successfully' });
  } catch (err: any) {
    console.error('Delete Conversation Error:', err);
    return res.status(500).json({ error: 'Failed to delete conversation' });
  }
});

// 5b. DELETE /api/v1/conversations - Delete all conversations for the authenticated user
conversationsRouter.delete('/', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = Number(req.user!.id);

    const deleted = await prisma.chatThread.deleteMany({
      where: { userId }
    });

    return res.json({ message: `Successfully deleted ${deleted.count} conversations` });
  } catch (err: any) {
    console.error('Delete All Conversations Error:', err);
    return res.status(500).json({ error: 'Failed to delete conversations' });
  }
});

// 6. GET /api/v1/conversations/:id/messages - Paginated messages for a conversation
conversationsRouter.get('/:id/messages', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = Number(req.user!.id);
    const conversationId = req.params.id;
    const page = Math.max(1, parseInt(req.query.page as string) || 1);
    const limit = Math.min(100, Math.max(1, parseInt(req.query.limit as string) || 50));
    const skip = (page - 1) * limit;

    const conversation = await prisma.chatThread.findFirst({
      where: { id: conversationId, userId }
    });

    if (!conversation) {
      return res.status(404).json({ error: 'Conversation not found or access denied' });
    }

    const [total, messages] = await Promise.all([
      prisma.message.count({ where: { threadId: conversationId } }),
      prisma.message.findMany({
        where: { threadId: conversationId },
        orderBy: { createdAt: 'asc' },
        skip,
        take: limit
      })
    ]);

    return res.json({
      messages,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit)
      }
    });
  } catch (err: any) {
    console.error('Get Messages Error:', err);
    return res.status(500).json({ error: 'Failed to fetch messages' });
  }
});

// 7. GET /api/v1/conversations/:id/runs - Get agent execution runs and tool calls for a conversation
conversationsRouter.get('/:id/runs', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = Number(req.user!.id);
    const conversationId = req.params.id;

    const conversation = await prisma.chatThread.findFirst({
      where: { id: conversationId, userId }
    });

    if (!conversation) {
      return res.status(404).json({ error: 'Conversation not found or access denied' });
    }

    const runs = await prisma.agentRun.findMany({
      where: { threadId: conversationId, userId },
      orderBy: { startedAt: 'desc' },
      include: {
        toolCalls: {
          orderBy: { startedAt: 'asc' }
        }
      }
    });

    return res.json({ runs });
  } catch (err: any) {
    console.error('Get Agent Runs Error:', err);
    return res.status(500).json({ error: 'Failed to fetch agent runs' });
  }
});

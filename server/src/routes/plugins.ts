import { Router, Response } from 'express';
import { z } from 'zod';
import { prisma } from '../config/prisma.js';
import { authenticateToken, AuthenticatedRequest } from '../middleware/auth.js';
import { SYSTEM_PLUGINS, PLUGIN_CATEGORIES } from '../config/pluginRegistry.js';

export const pluginsRouter = Router();

// Require authentication for all plugin endpoints
pluginsRouter.use(authenticateToken);

const CustomPluginSchema = z.object({
  name: z.string().trim().min(1).max(100),
  description: z.string().trim().min(1).max(500),
  icon: z.string().trim().max(10).optional().default('⚡'),
  category: z.string().trim().max(50).optional().default('custom'),
  endpointUrl: z.string().trim().url(),
  method: z.enum(['GET', 'POST']).optional().default('POST'),
  params: z.any().optional()
});

const TogglePreferenceSchema = z.object({
  enabled: z.boolean()
});

// 1. GET /api/v1/plugins - Get all plugins with live availability and user persistent state
pluginsRouter.get('/', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = Number(req.user!.id);

    // Fetch user preferences and custom plugins in parallel from PostgreSQL
    const [userPrefs, customPlugins] = await Promise.all([
      prisma.userPluginPreference.findMany({
        where: { userId }
      }),
      prisma.customPlugin.findMany({
        where: { userId },
        orderBy: { createdAt: 'desc' }
      })
    ]);

    const prefMap = new Map<string, boolean>();
    for (const p of userPrefs) {
      prefMap.set(p.pluginId, p.isEnabled);
    }

    // Run dynamic live availability check for system plugins in parallel
    const systemPluginsWithStatus = await Promise.all(
      SYSTEM_PLUGINS.map(async (sp) => {
        let availability = { isAvailable: true, statusMessage: 'Active & Available' };
        try {
          availability = await sp.checkAvailability();
        } catch (err: any) {
          availability = { isAvailable: false, statusMessage: 'Service Degraded' };
        }

        const isUserEnabled = prefMap.has(sp.id)
          ? prefMap.get(sp.id)!
          : sp.isEnabledByDefault;

        return {
          id: sp.id,
          name: sp.name,
          description: sp.description,
          icon: sp.icon,
          category: sp.category,
          enabled: isUserEnabled,
          isAvailable: availability.isAvailable,
          statusMessage: availability.statusMessage,
          isCustom: false,
          author: sp.author,
          version: sp.version
        };
      })
    );

    // Format custom plugins
    const customPluginsFormatted = customPlugins.map(cp => {
      const isUserEnabled = prefMap.has(cp.id)
        ? prefMap.get(cp.id)!
        : cp.isEnabled;

      return {
        id: cp.id,
        name: cp.name,
        description: cp.description,
        icon: cp.icon || '⚡',
        category: cp.category || 'custom',
        enabled: isUserEnabled,
        isAvailable: true,
        statusMessage: 'Custom Webhook Active',
        isCustom: true,
        author: 'User Defined',
        version: '1.0.0',
        endpointUrl: cp.endpointUrl,
        method: cp.method as 'GET' | 'POST',
        params: cp.params
      };
    });

    const allPlugins = [...systemPluginsWithStatus, ...customPluginsFormatted];

    // Compute dynamic categories present in active plugins
    const existingCatIds = new Set(allPlugins.map(p => p.category));
    const dynamicCategories = PLUGIN_CATEGORIES.filter(
      c => c.id === 'all' || existingCatIds.has(c.id)
    );

    return res.json({
      plugins: allPlugins,
      categories: dynamicCategories,
      totalCount: allPlugins.length,
      availableCount: allPlugins.filter(p => p.isAvailable).length
    });
  } catch (err: any) {
    console.error('Fetch Plugins Error:', err);
    return res.status(500).json({ error: 'Failed to fetch dynamic plugins' });
  }
});

// 2. PATCH /api/v1/plugins/toggle/:pluginId - Persist user plugin toggle state in PostgreSQL
pluginsRouter.patch('/toggle/:pluginId', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = Number(req.user!.id);
    const pluginId = req.params.pluginId;

    const parseResult = TogglePreferenceSchema.safeParse(req.body);
    if (!parseResult.success) {
      return res.status(400).json({ error: 'Invalid toggle body' });
    }

    const { enabled } = parseResult.data;

    const preference = await prisma.userPluginPreference.upsert({
      where: {
        userId_pluginId: {
          userId,
          pluginId
        }
      },
      create: {
        userId,
        pluginId,
        isEnabled: enabled
      },
      update: {
        isEnabled: enabled,
        updatedAt: new Date()
      }
    });

    return res.json({
      message: 'Plugin preference updated successfully',
      preference
    });
  } catch (err: any) {
    console.error('Toggle Plugin Error:', err);
    return res.status(500).json({ error: 'Failed to update plugin preference' });
  }
});

// 3. POST /api/v1/plugins/custom - Create a custom user tool in PostgreSQL
pluginsRouter.post('/custom', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = Number(req.user!.id);
    const parseResult = CustomPluginSchema.safeParse(req.body);
    if (!parseResult.success) {
      return res.status(400).json({
        error: 'Validation failed',
        details: parseResult.error.errors.map(e => e.message).join(', ')
      });
    }

    const { name, description, icon, category, endpointUrl, method, params } = parseResult.data;

    const customPlugin = await prisma.customPlugin.create({
      data: {
        userId,
        name,
        description,
        icon: icon || '⚡',
        category: category || 'custom',
        endpointUrl,
        method: method || 'POST',
        params: params || undefined,
        isEnabled: true
      }
    });

    // Also enable by default in preferences
    await prisma.userPluginPreference.upsert({
      where: {
        userId_pluginId: {
          userId,
          pluginId: customPlugin.id
        }
      },
      create: {
        userId,
        pluginId: customPlugin.id,
        isEnabled: true
      },
      update: {
        isEnabled: true
      }
    });

    return res.status(201).json({
      message: 'Custom tool registered successfully',
      plugin: {
        id: customPlugin.id,
        name: customPlugin.name,
        description: customPlugin.description,
        icon: customPlugin.icon,
        category: customPlugin.category,
        enabled: true,
        isAvailable: true,
        statusMessage: 'Custom Webhook Active',
        isCustom: true,
        author: 'User Defined',
        version: '1.0.0',
        endpointUrl: customPlugin.endpointUrl,
        method: customPlugin.method,
        params: customPlugin.params
      }
    });
  } catch (err: any) {
    console.error('Create Custom Plugin Error:', err);
    return res.status(500).json({ error: 'Failed to register custom tool' });
  }
});

// 4. DELETE /api/v1/plugins/custom/:id - Delete a user's custom plugin
pluginsRouter.delete('/custom/:id', async (req: AuthenticatedRequest, res: Response) => {
  try {
    const userId = Number(req.user!.id);
    const pluginId = req.params.id;

    const existing = await prisma.customPlugin.findFirst({
      where: { id: pluginId, userId }
    });

    if (!existing) {
      return res.status(404).json({ error: 'Custom plugin not found or access denied' });
    }

    await Promise.all([
      prisma.customPlugin.delete({ where: { id: pluginId } }),
      prisma.userPluginPreference.deleteMany({ where: { userId, pluginId } })
    ]);

    return res.json({ message: 'Custom tool deleted successfully' });
  } catch (err: any) {
    console.error('Delete Custom Plugin Error:', err);
    return res.status(500).json({ error: 'Failed to delete custom tool' });
  }
});

// Common Central Base URL Configuration
const envBaseUrl = typeof import.meta !== 'undefined' && (import.meta as any).env 
  ? (import.meta as any).env.VITE_API_BASE_URL 
  : '';

export const API_BASE_URL = (envBaseUrl || '/api/v1').replace(/\/$/, '');

/**
 * Universal API Fetch Helper
 * Prepends API_BASE_URL and automatically attaches JWT Bearer token if present.
 */
export async function apiFetch<T = any>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('clever_jwt_token');
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  
  // Normalize URL path to prevent duplicate /api/v1 prefixes
  const fullUrl = cleanEndpoint.startsWith('/api') 
    ? cleanEndpoint 
    : `${API_BASE_URL}${cleanEndpoint}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(fullUrl, {
    ...options,
    headers,
  });

  const text = await response.text();
  let data: any = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text };
    }
  }

  if (!response.ok) {
    throw new Error(data.error || data.detail || data.message || `Request failed with status ${response.status}`);
  }

  return data as T;
}

// Modular API Client Endpoints
export const apiClient = {
  baseUrl: API_BASE_URL,
  
  // Auth Endpoints
  auth: {
    login: (credentials: { email: string; password: string; rememberMe?: boolean }) =>
      apiFetch('/auth/login', { method: 'POST', body: JSON.stringify(credentials) }),
    
    signup: (userData: { name: string; email: string; password: string; rememberMe?: boolean }) =>
      apiFetch('/auth/signup', { method: 'POST', body: JSON.stringify(userData) }),
    
    google: (payload: { credential?: string; email?: string; name?: string; avatarUrl?: string; googleId?: string }) =>
      apiFetch('/auth/google', { method: 'POST', body: JSON.stringify(payload) }),
    
    me: () => apiFetch('/auth/me', { method: 'GET' })
  },

  // Chat Endpoints
  chat: {
    sendMessage: (payload: { message: string; threadId?: string; model?: string; activePlugins?: string[]; documentIds?: string[] }) => {
      const cleanPayload: Record<string, any> = {
        message: payload.message
      };
      if (payload.threadId) cleanPayload.threadId = payload.threadId;
      if (payload.model && payload.model.trim()) cleanPayload.model = payload.model.trim();
      if (payload.activePlugins) cleanPayload.activePlugins = payload.activePlugins;
      if (payload.documentIds && payload.documentIds.length > 0) cleanPayload.documentIds = payload.documentIds;

      return apiFetch('/chat', { method: 'POST', body: JSON.stringify(cleanPayload) });
    },

    // Kicks off an agent run asynchronously (HTTP 202 + runId) — the actual agent
    // work happens in the background; callers must poll `getRunStatus` or, better,
    // subscribe to `streamRunEvents` for live SSE progress.
    sendMessageAsync: (payload: { message: string; threadId?: string; model?: string; activePlugins?: string[]; documentIds?: string[] }) => {
      const cleanPayload: Record<string, any> = {
        message: payload.message
      };
      if (payload.threadId) cleanPayload.threadId = payload.threadId;
      if (payload.model && payload.model.trim()) cleanPayload.model = payload.model.trim();
      if (payload.activePlugins) cleanPayload.activePlugins = payload.activePlugins;
      if (payload.documentIds && payload.documentIds.length > 0) cleanPayload.documentIds = payload.documentIds;

      return apiFetch('/chat?async=true', { method: 'POST', body: JSON.stringify(cleanPayload) });
    },

    getRunStatus: (runId: string) => apiFetch(`/chat/runs/${runId}`, { method: 'GET' }),

    cancelRun: (runId: string) => apiFetch(`/chat/runs/${runId}/cancel`, { method: 'POST' }),

    // Retries a FAILED/TIMEOUT/NO_RESULTS/CANCELLED run by starting a fresh run
    // with the same prompt — powers the UI's [Retry] affordance.
    retryRun: (runId: string) => apiFetch(`/chat/runs/${runId}/retry`, { method: 'POST' }),

    // Resumes a WAITING_FOR_USER run (e.g. after completing a login in the
    // connected browser) — powers the UI's [Continue] affordance.
    continueRun: (runId: string, message?: string) =>
      apiFetch(`/chat/runs/${runId}/continue`, { method: 'POST', body: JSON.stringify({ message: message || '' }) }),

    /**
     * Subscribes to the Server-Sent Events stream for a live agent run and invokes
     * `onEvent` for every parsed SSE frame (`{type, ...}`). Uses `fetch` + a manual
     * reader instead of `EventSource` so the JWT Authorization header can be attached
     * (native EventSource has no header support). Returns an `AbortController` the
     * caller can use to cancel the subscription (e.g. on unmount).
     */
    streamRunEvents: (runId: string, onEvent: (event: any) => void, onError?: (err: Error) => void): AbortController => {
      const controller = new AbortController();
      const token = localStorage.getItem('clever_jwt_token');
      const url = `${API_BASE_URL}/chat/runs/${runId}/events`;

      (async () => {
        try {
          const response = await fetch(url, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
            signal: controller.signal
          });

          if (!response.ok || !response.body) {
            throw new Error(`Failed to open event stream (status ${response.status})`);
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const frames = buffer.split('\n\n');
            buffer = frames.pop() || '';

            for (const frame of frames) {
              const line = frame.split('\n').find(l => l.startsWith('data:'));
              if (!line) continue;
              try {
                onEvent(JSON.parse(line.slice(5).trim()));
              } catch {
                // Ignore malformed frames rather than killing the whole stream.
              }
            }
          }
        } catch (err: any) {
          if (err?.name !== 'AbortError') {
            onError?.(err instanceof Error ? err : new Error(String(err)));
          }
        }
      })();

      return controller;
    },

    getHistory: () => apiFetch('/chat/history', { method: 'GET' }),

    clearHistory: () => apiFetch('/chat/history', { method: 'DELETE' })
  },

  // Conversations Lifecycle & Deletion Endpoints
  conversations: {
    list: (params?: { page?: number; limit?: number; category?: string; search?: string }) => {
      const query = new URLSearchParams();
      if (params?.page) query.set('page', String(params.page));
      if (params?.limit) query.set('limit', String(params.limit));
      if (params?.category) query.set('category', params.category);
      if (params?.search) query.set('search', params.search);
      const qs = query.toString();
      return apiFetch(`/conversations${qs ? `?${qs}` : ''}`, { method: 'GET' });
    },

    get: (id: string) => apiFetch(`/conversations/${id}`, { method: 'GET' }),

    update: (id: string, payload: { title?: string; category?: string }) =>
      apiFetch(`/conversations/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),

    delete: (id: string) => apiFetch(`/conversations/${id}`, { method: 'DELETE' }),

    clearAll: () => apiFetch('/conversations', { method: 'DELETE' })
  },

  // Document Attachment Endpoints (MarkItDown RAG Pipeline)
  documents: {
    upload: async (file: File) => {
      const token = localStorage.getItem('clever_jwt_token');
      const response = await fetch(`${API_BASE_URL}/documents/upload`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/octet-stream',
          'x-document-filename': file.name,
          'x-document-mime-type': file.type || 'application/octet-stream',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: await file.arrayBuffer()
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Failed to convert document.');
      }
      return data as { document: { id: string; filename: string; sizeBytes: number; chunkCount: number } };
    }
  },

  // Dynamic Plugins & Tools Registry Endpoints
  plugins: {
    list: () => apiFetch('/plugins', { method: 'GET' }),

    toggle: (pluginId: string, enabled: boolean) =>
      apiFetch(`/plugins/toggle/${pluginId}`, { method: 'PATCH', body: JSON.stringify({ enabled }) }),

    createCustom: (payload: { name: string; description: string; icon?: string; category?: string; endpointUrl: string; method?: string; params?: any }) =>
      apiFetch('/plugins/custom', { method: 'POST', body: JSON.stringify(payload) }),

    deleteCustom: (id: string) =>
      apiFetch(`/plugins/custom/${id}`, { method: 'DELETE' })
  },

  // Production Browser AI Agent Platform Endpoints
  browser: {
    getStatus: () => apiFetch('/browser/status', { method: 'GET' }),

    connect: (payload?: { mode?: string; cdpUrl?: string; userDataDir?: string }) =>
      apiFetch('/browser/connect', { method: 'POST', body: JSON.stringify(payload || {}) }),

    disconnect: () => apiFetch('/browser/disconnect', { method: 'POST' }),

    getTabs: () => apiFetch('/browser/tabs', { method: 'GET' }),

    selectTab: (tabId: string) =>
      apiFetch('/browser/tabs/select', { method: 'POST', body: JSON.stringify({ tabId }) }),

    openTab: (url: string) =>
      apiFetch('/browser/tabs/open', { method: 'POST', body: JSON.stringify({ url }) }),

    closeTab: (tabId: string) =>
      apiFetch('/browser/tabs/close', { method: 'POST', body: JSON.stringify({ tabId }) }),

    // Stagehand-powered instruction-based primitives (no selectors/element IDs —
    // Stagehand's AI resolves the target from plain natural language).
    navigate: (url: string) =>
      apiFetch('/browser/navigate', { method: 'POST', body: JSON.stringify({ url }) }),

    act: (instruction: string, confirmed: boolean = false) =>
      apiFetch('/browser/act', { method: 'POST', body: JSON.stringify({ instruction, confirmed }) }),

    observe: (instruction?: string) =>
      apiFetch('/browser/observe', { method: 'POST', body: JSON.stringify({ instruction }) }),

    extract: (instruction: string) =>
      apiFetch('/browser/extract', { method: 'POST', body: JSON.stringify({ instruction }) }),

    confirmAction: (payload: { confirmationId: string; approved: boolean }) =>
      apiFetch('/browser/confirm', { method: 'POST', body: JSON.stringify(payload) })
  }
};

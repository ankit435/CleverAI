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
    sendMessage: (payload: { message: string; threadId?: string; model?: string; activePlugins?: string[]; documentIds?: string[] }) =>
      apiFetch('/chat', { method: 'POST', body: JSON.stringify(payload) }),
    
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
  }
};

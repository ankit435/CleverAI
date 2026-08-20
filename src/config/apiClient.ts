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

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || data.detail || `Request failed with status ${response.status}`);
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
    sendMessage: (payload: { message: string; threadId?: string; model?: string; activePlugins?: string[] }) =>
      apiFetch('/chat', { method: 'POST', body: JSON.stringify(payload) }),
    
    getHistory: () => apiFetch('/chat/history', { method: 'GET' })
  }
};

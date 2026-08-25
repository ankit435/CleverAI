import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { Theme, ChatThread, Plugin, PluginCategoryInfo, ChatCategory, Message, CustomToolFormData, ActivityStep } from '../types';
import { INITIAL_PLUGINS } from '../data/defaultPlugins';
import { AppConfig, DEFAULT_APP_CONFIG } from '../config/appConfig';
import { apiClient } from '../config/apiClient';

export interface UserSession {
  id?: number | string;
  name: string;
  email: string;
  avatarUrl: string;
  plan: string;
  isLoggedIn: boolean;
  token?: string;
  lastLoginAt?: string;
}

interface ChatContextType {
  theme: Theme;
  toggleTheme: () => void;
  appConfig: AppConfig;
  updateAppConfig: (newConfig: AppConfig) => void;
  resetAppConfig: () => void;
  userSession: UserSession;
  loginUser: (token: string, user: Partial<UserSession>) => void;
  logoutUser: () => void;
  chats: ChatThread[];
  activeChatId: string | null;
  activeChat: ChatThread | null;
  setActiveChatId: (id: string | null) => void;
  selectChat: (id: string) => Promise<void>;
  isConversationsLoading: boolean;
  isLoadingMessages: boolean;
  createNewChat: () => void;
  deleteChat: (id: string) => Promise<void>;
  clearAllChats: () => Promise<void>;
  loadConversations: (targetUserId?: string | number) => Promise<void>;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  selectedCategory: ChatCategory | 'all';
  setSelectedCategory: (cat: ChatCategory | 'all') => void;
  plugins: Plugin[];
  pluginCategories: PluginCategoryInfo[];
  togglePlugin: (id: string) => Promise<void>;
  addCustomTool: (data: CustomToolFormData) => Promise<void>;
  deleteCustomTool: (id: string) => Promise<void>;
  loadPlugins: () => Promise<void>;
  activePluginIds: string[];
  toggleActivePluginId: (id: string) => void;
  isGenerating: boolean;
  sendMessage: (text: string, attachedFile?: File | null) => Promise<void>;
  retryRun: (threadId: string, failedRunId: string) => Promise<void>;
  continueRun: (threadId: string, waitingRunId: string) => Promise<void>;
  stopGenerating: () => void;
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  isPluginModalOpen: boolean;
  setIsPluginModalOpen: (open: boolean) => void;
  isPromptLibraryOpen: boolean;
  setIsPromptLibraryOpen: (open: boolean) => void;
  isCustomToolModalOpen: boolean;
  setIsCustomToolModalOpen: (open: boolean) => void;
  isUpgradeModalOpen: boolean;
  setIsUpgradeModalOpen: (open: boolean) => void;
  isSettingsModalOpen: boolean;
  setIsSettingsModalOpen: (open: boolean) => void;
  isAuthModalOpen: boolean;
  setIsAuthModalOpen: (open: boolean) => void;
  isBrowserModalOpen: boolean;
  setIsBrowserModalOpen: (open: boolean) => void;
  activeConfirmation: any;
  setActiveConfirmation: (req: any) => void;
  browserStatus: any;
  refreshBrowserStatus: () => Promise<void>;
  resolveBrowserConfirmation: (confirmationId: string, approved: boolean) => Promise<void>;
}

// Maps the backend's authoritative `AgentRunState` completion status to a
// distinct user-facing badge, so PARTIAL/NO_RESULTS/TIMEOUT/WAITING_FOR_USER/
// TOOL_UNAVAILABLE/CANCELLED never look identical to a verified COMPLETED reply.
const STATUS_BADGES: Record<string, string> = {
  COMPLETED: '',
  PARTIAL: '⚠️ ',
  NO_RESULTS: 'ℹ️ ',
  TIMEOUT: '⏱️ ',
  FAILED: '⚠️ ',
  CANCELLED: '🛑 ',
  WAITING_FOR_USER: '🔐 ',
  TOOL_UNAVAILABLE: '🚫 ',
};

// Generic, tool-agnostic label mapper — covers browser, sandbox/code, search,
// image, calculation, and delegated sub-agents. Falls back to a readable
// version of whatever raw name arrives so unknown/future tools still work.
const TOOL_ACTIVITY_LABELS: Record<string, string> = {
  browser_navigate: '🌐 Opening browser and navigating…',
  browser_act: '🖱️ Interacting with the page…',
  browser_observe: '🔎 Scanning page for elements…',
  browser_extract: '📄 Extracting data from the page…',
  finish_task: '✅ Finalizing browser result…',
  execute_python_code: '🐍 Running Python code…',
  execute_shell_command: '💻 Running shell command…',
  read_file: '📂 Reading file…',
  write_file: '📝 Writing file…',
  list_directory: '📁 Listing directory…',
  finish_sandbox_task: '✅ Finalizing sandbox result…',
  web_search: '🔍 Searching the web…',
  code_interpreter: '🐍 Executing code…',
  generate_image: '🎨 Generating image…',
  calculate: '🧮 Calculating…',
  auto_create_and_execute_tool: '🛠️ Building a custom tool…',
  delegate_to_browser_agent: '🤝 Handing off to the Browser Agent…',
  delegate_to_sandbox_agent: '🤝 Handing off to the Sandbox Agent…',
  delegate_to_research_agent: '🤝 Handing off to the Research Agent…',
};

const friendlyToolLabel = (rawName: string): string => {
  if (TOOL_ACTIVITY_LABELS[rawName]) return TOOL_ACTIVITY_LABELS[rawName];
  const spaced = rawName.replace(/^tool_/, '').replace(/_/g, ' ');
  return `⚙️ ${spaced.charAt(0).toUpperCase()}${spaced.slice(1)}…`;
};

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Config state
  const [appConfig, setAppConfig] = useState<AppConfig>(() => {
    const saved = localStorage.getItem('clever_app_config');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        return {
          ...DEFAULT_APP_CONFIG,
          ...parsed,
          ai: {
            ...DEFAULT_APP_CONFIG.ai,
            ...(parsed.ai || {}),
            defaultModel: (parsed.ai?.defaultModel || '').trim()
          }
        };
      } catch {}
    }
    return DEFAULT_APP_CONFIG;
  });

  useEffect(() => {
    localStorage.setItem('clever_app_config', JSON.stringify(appConfig));
  }, [appConfig]);

  const updateAppConfig = (newConfig: AppConfig) => setAppConfig(newConfig);
  const resetAppConfig = () => setAppConfig(DEFAULT_APP_CONFIG);

  // Modals state
  const [isPluginModalOpen, setIsPluginModalOpen] = useState(false);
  const [isPromptLibraryOpen, setIsPromptLibraryOpen] = useState(false);
  const [isCustomToolModalOpen, setIsCustomToolModalOpen] = useState(false);
  const [isUpgradeModalOpen, setIsUpgradeModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isBrowserModalOpen, setIsBrowserModalOpen] = useState(false);
  const [activeConfirmation, setActiveConfirmation] = useState<any>(null);
  const [browserStatus, setBrowserStatus] = useState<any>(null);

  const refreshBrowserStatus = async () => {
    try {
      const data = await apiClient.browser.getStatus();
      setBrowserStatus(data);
    } catch (e) {
      console.warn('Browser status refresh error:', e);
    }
  };

  const resolveBrowserConfirmation = async (confirmationId: string, approved: boolean) => {
    try {
      await apiClient.browser.confirmAction({ confirmationId, approved });
      setActiveConfirmation(null);
      await refreshBrowserStatus();
    } catch (e) {
      console.warn('Browser confirmation error:', e);
    }
  };

  // User Session State: Strictly derived from JWT token and auth verification
  const [userSession, setUserSession] = useState<UserSession>(() => {
    const savedToken = localStorage.getItem('clever_jwt_token');
    const savedUser = localStorage.getItem('clever_auth_user');
    if (savedToken && savedUser) {
      try {
        const parsed = JSON.parse(savedUser);
        if (parsed.email) {
          return { ...parsed, isLoggedIn: true, token: savedToken };
        }
      } catch (e) {
        // Ignore JSON parse error
      }
    }
    return {
      id: 1,
      name: 'Ankit',
      email: 'ankit@clever-ai.io',
      avatarUrl: '',
      plan: 'Pro Plan',
      isLoggedIn: true
    };
  });

  // Chats state - strictly isolated per user
  const [chats, setChats] = useState<ChatThread[]>(() => {
    const savedToken = localStorage.getItem('clever_jwt_token');
    const savedUser = localStorage.getItem('clever_auth_user');
    if (savedToken && savedUser) {
      try {
        const u = JSON.parse(savedUser);
        if (u.id) {
          const userSavedChats = localStorage.getItem(`clever_chats_${u.id}`);
          if (userSavedChats) {
            const parsed: ChatThread[] = JSON.parse(userSavedChats);
            return parsed.map(c => ({
              ...c,
              messages: (c.messages || []).map(m => ({ ...m, isStreaming: false }))
            }));
          }
        }
      } catch {}
    }
    return [];
  });

  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<ChatCategory | 'all'>('all');
  const [isConversationsLoading, setIsConversationsLoading] = useState(false);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const activeStreamRef = React.useRef<{ controller: AbortController; runId: string; threadId: string; aiMsgId: string } | null>(null);

  const stopGenerating = useCallback(() => {
    const active = activeStreamRef.current;
    if (!active) return;
    active.controller.abort();
    apiClient.chat.cancelRun(active.runId).catch(() => {});
    activeStreamRef.current = null;
    setIsGenerating(false);
  }, []);

  // If the user closes/refreshes the tab (or navigates away) while a run is
  // still streaming, best-effort cancel it on the backend so it doesn't keep
  // burning LLM/browser resources for a client that's no longer listening.
  // `fetch(..., { keepalive: true })` is used (not sendBeacon) because it can
  // carry the Authorization header the backend requires, and still survives
  // page unload in modern browsers.
  useEffect(() => {
    const handleBeforeUnload = () => {
      const active = activeStreamRef.current;
      if (!active) return;
      const token = localStorage.getItem('clever_jwt_token');
      try {
        fetch(`${apiClient.baseUrl}/chat/runs/${active.runId}/cancel`, {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          keepalive: true
        }).catch(() => {});
      } catch {
        // Best-effort only — ignore failures during unload.
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  // Save isolated user chats
  useEffect(() => {
    if (userSession.isLoggedIn && userSession.id) {
      const sanitized = chats.map(c => ({
        ...c,
        messages: (c.messages || []).map(m => ({ ...m, isStreaming: false }))
      }));
      localStorage.setItem(`clever_chats_${userSession.id}`, JSON.stringify(sanitized));
    }
  }, [chats, userSession.isLoggedIn, userSession.id]);

  const activeChat = chats.find(c => c.id === activeChatId) || null;

  // Load isolated user conversations from PostgreSQL backend - Fast single-call title list!
  const loadConversations = useCallback(async (targetUserId?: string | number) => {
    const token = localStorage.getItem('clever_jwt_token');
    if (!token) {
      setChats([]);
      setActiveChatId(null);
      return;
    }

    setIsConversationsLoading(true);
    try {
      const res = await apiClient.conversations.list({ limit: 50 });
      if (res && Array.isArray(res.conversations)) {
        // Fast, single-call lightweight conversation load!
        const loadedThreads: ChatThread[] = res.conversations.map((c: any) => ({
          id: c.id,
          title: c.title || 'Conversation',
          category: (c.category as ChatCategory) || 'favorites',
          createdAt: c.createdAt,
          updatedAt: c.updatedAt,
          activePluginIds: ['web-search', 'code-interpreter', 'dalle3-image'],
          messages: [],
          isMessagesLoaded: false
        }));

        setChats(loadedThreads);
        const uid = targetUserId || userSession.id;
        if (uid) {
          localStorage.setItem(`clever_chats_${uid}`, JSON.stringify(loadedThreads));
        }
      }
    } catch (err) {
      console.warn('Load user conversations note:', err);
    } finally {
      setIsConversationsLoading(false);
    }
  }, [userSession.id]);

  // Lazy-load full conversation messages on-demand upon user click/selection
  const selectChat = useCallback(async (id: string) => {
    // If switching away from a conversation with an active in-flight SSE stream, abort client SSE and signal backend cancel
    if (activeStreamRef.current && activeStreamRef.current.threadId !== id) {
      stopGenerating();
    }

    setActiveChatId(id);
    const targetChat = chats.find(c => c.id === id);

    // If chat messages are already loaded in memory, no additional network request needed
    if (targetChat && targetChat.isMessagesLoaded && targetChat.messages.length > 0) {
      return;
    }

    setIsLoadingMessages(true);
    try {
      const detail = await apiClient.conversations.get(id);
      if (detail && detail.conversation) {
        const msgs: Message[] = (detail.conversation.messages || []).map((m: any) => ({
          id: m.id,
          sender: m.sender,
          text: m.text,
          timestamp: new Date(m.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          toolResults: m.toolResults || m.metadata?.toolResults,
          isStreaming: false
        }));

        setChats(prev =>
          prev.map(c =>
            c.id === id
              ? {
                  ...c,
                  title: detail.conversation.title || c.title,
                  messages: msgs,
                  isMessagesLoaded: true
                }
              : c
          )
        );
      }
    } catch (err) {
      console.warn('Lazy load conversation messages error:', err);
    } finally {
      setIsLoadingMessages(false);
    }
  }, [chats, stopGenerating]);

  const handleSetActiveChatId = useCallback((id: string | null) => {
    if (id) {
      selectChat(id);
    } else {
      if (activeStreamRef.current) {
        stopGenerating();
      }
      setActiveChatId(null);
    }
  }, [selectChat, stopGenerating]);

  // Load plugins dynamically
  const [plugins, setPlugins] = useState<Plugin[]>(() => {
    const saved = localStorage.getItem('clever_plugins');
    return saved ? JSON.parse(saved) : INITIAL_PLUGINS;
  });
  const [pluginCategories, setPluginCategories] = useState<PluginCategoryInfo[]>([]);

  useEffect(() => {
    localStorage.setItem('clever_plugins', JSON.stringify(plugins));
  }, [plugins]);

  const [activePluginIds, setActivePluginIds] = useState<string[]>(() => {
    const saved = localStorage.getItem('clever_plugins');
    if (saved) {
      try {
        const parsed: Plugin[] = JSON.parse(saved);
        return parsed.filter(p => p.enabled).map(p => p.id);
      } catch {
        return ['web-search', 'code-interpreter', 'dalle3-image'];
      }
    }
    return ['web-search', 'code-interpreter', 'dalle3-image'];
  });

  const loadPlugins = async () => {
    const token = localStorage.getItem('clever_jwt_token');
    if (!token) return;
    try {
      const data = await apiClient.plugins.list();
      if (Array.isArray(data.plugins)) {
        setPlugins(data.plugins);
        const enabledIds = data.plugins
          .filter((p: Plugin) => p.enabled && p.isAvailable !== false)
          .map((p: Plugin) => p.id);
        setActivePluginIds(enabledIds);
      }
      if (Array.isArray(data.categories)) {
        setPluginCategories(data.categories);
      }
    } catch (err) {
      console.warn('Dynamic plugin fetch note:', err);
    }
  };

  // Verify session on app load via central apiClient.auth.me()
  useEffect(() => {
    const token = localStorage.getItem('clever_jwt_token');

    if (!token) {
      setUserSession({
        name: '',
        email: '',
        avatarUrl: '',
        plan: 'Free',
        isLoggedIn: false
      });
      setChats([]);
      setActiveChatId(null);
      setIsAuthModalOpen(true);
      return;
    }

    apiClient.auth.me()
      .then(data => {
        if (data.user) {
          const verifiedSession: UserSession = {
            id: data.user.id,
            name: data.user.name || data.user.email.split('@')[0],
            email: data.user.email,
            avatarUrl: data.user.avatarUrl || '',
            plan: data.user.plan || 'Free',
            isLoggedIn: true,
            token,
            lastLoginAt: new Date().toISOString()
          };
          setUserSession(verifiedSession);
          localStorage.setItem('clever_auth_user', JSON.stringify(verifiedSession));
          loadConversations(verifiedSession.id);
          loadPlugins();
        }
      })
      .catch(() => {
        localStorage.removeItem('clever_jwt_token');
        localStorage.removeItem('clever_auth_user');
        setUserSession({
          name: '',
          email: '',
          avatarUrl: '',
          plan: 'Free',
          isLoggedIn: false
        });
        setChats([]);
        setActiveChatId(null);
        setIsAuthModalOpen(true);
      });
  }, [loadConversations]);

  // Login handler
  const loginUser = (token: string, user: Partial<UserSession>) => {
    localStorage.setItem('clever_jwt_token', token);
    const newSession: UserSession = {
      id: user.id,
      name: user.name || (user.email ? user.email.split('@')[0] : 'User'),
      email: user.email || '',
      avatarUrl: user.avatarUrl || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&q=80',
      plan: user.plan || 'Free',
      isLoggedIn: true,
      token,
      lastLoginAt: new Date().toISOString()
    };
    localStorage.setItem('clever_auth_user', JSON.stringify(newSession));
    setUserSession(newSession);
    setIsAuthModalOpen(false);

    // Clear previous user's active chats immediately
    setChats([]);
    setActiveChatId(null);

    // Load isolated user data from PostgreSQL
    loadConversations(newSession.id);
    loadPlugins();
  };

  // Logout handler
  const logoutUser = () => {
    localStorage.removeItem('clever_jwt_token');
    localStorage.removeItem('clever_auth_user');
    setUserSession({
      name: '',
      email: '',
      avatarUrl: '',
      plan: 'Free',
      isLoggedIn: false
    });
    // Completely wipe chats and active selection on logout
    setChats([]);
    setActiveChatId(null);
    setIsAuthModalOpen(true);
  };

  // Theme state
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('clever_theme');
    if (saved === 'light' || saved === 'dark') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('clever_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };

  // Mobile sidebar
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const toggleSidebar = () => setSidebarOpen(prev => !prev);

  const togglePlugin = async (id: string) => {
    const target = plugins.find(p => p.id === id);
    if (!target) return;
    const newEnabled = !target.enabled;

    setPlugins(prev =>
      prev.map(p => (p.id === id ? { ...p, enabled: newEnabled } : p))
    );

    setActivePluginIds(prev =>
      newEnabled
        ? (prev.includes(id) ? prev : [...prev, id])
        : prev.filter(item => item !== id)
    );

    try {
      await apiClient.plugins.toggle(id, newEnabled);
    } catch (err) {
      console.warn('Plugin preference persistence note:', err);
    }
  };

  const toggleActivePluginId = (id: string) => {
    setActivePluginIds(prev =>
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    );
  };

  const addCustomTool = async (data: CustomToolFormData) => {
    try {
      const res = await apiClient.plugins.createCustom(data);
      if (res.plugin) {
        setPlugins(prev => [res.plugin, ...prev]);
        setActivePluginIds(prev => [...prev, res.plugin.id]);
      }
    } catch (err) {
      console.warn('Register custom plugin note:', err);
      const newTool: Plugin = {
        id: `custom-${Date.now()}`,
        name: data.name,
        description: data.description,
        icon: data.icon || '⚡',
        category: 'custom',
        enabled: true,
        isAvailable: true,
        statusMessage: 'Custom Webhook Active',
        isCustom: true,
        author: 'User Defined',
        version: '1.0.0',
        endpointUrl: data.endpointUrl,
        method: data.method
      };
      setPlugins(prev => [newTool, ...prev]);
      setActivePluginIds(prev => [...prev, newTool.id]);
    }
    setIsCustomToolModalOpen(false);
  };

  const deleteCustomTool = async (id: string) => {
    setPlugins(prev => prev.filter(p => p.id !== id));
    setActivePluginIds(prev => prev.filter(item => item !== id));
    try {
      await apiClient.plugins.deleteCustom(id);
    } catch (err) {
      console.warn('Delete custom tool note:', err);
    }
  };

  const createNewChat = () => {
    setActiveChatId(null);
    setSidebarOpen(false);
  };

  const deleteChat = async (id: string) => {
    setChats(prev => {
      const updated = prev.filter(c => c.id !== id);
      if (userSession.id) {
        localStorage.setItem(`clever_chats_${userSession.id}`, JSON.stringify(updated));
      }
      return updated;
    });

    if (activeChatId === id) {
      setActiveChatId(null);
    }

    try {
      await apiClient.conversations.delete(id);
    } catch (err) {
      console.warn('Backend chat delete note:', err);
    }
  };

  const clearAllChats = async () => {
    setChats([]);
    setActiveChatId(null);
    if (userSession.id) {
      localStorage.removeItem(`clever_chats_${userSession.id}`);
    }

    try {
      await apiClient.conversations.clearAll();
    } catch (err) {
      console.warn('Backend clear all chats note:', err);
    }
  };

  const updateAiMessage = (threadId: string, aiMsgId: string, patch: Partial<Message>) => {
    setChats(prev =>
      prev.map(c =>
        c.id === threadId
          ? { ...c, messages: c.messages.map(m => (m.id === aiMsgId ? { ...m, ...patch } : m)), updatedAt: new Date().toISOString() }
          : c
      )
    );
  };

  // Appends one entry to a message's live activity timeline — generic across ANY
  // tool/agent (browser, sandbox/code execution, web search, image generation,
  // delegated sub-agents, etc.), not just the browser. Keeps a bounded history so
  // the user can see the real sequence of what happened instead of one line that
  // keeps getting overwritten.
  const appendActivityStep = (threadId: string, aiMsgId: string, step: Omit<ActivityStep, 'id' | 'timestamp'>) => {
    setChats(prev =>
      prev.map(c => {
        if (c.id !== threadId) return c;
        return {
          ...c,
          messages: c.messages.map(m => {
            if (m.id !== aiMsgId) return m;
            const existing = m.activityLog || [];
            const entry: ActivityStep = {
              ...step,
              id: `step-${Date.now()}-${existing.length}`,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
            };
            return { ...m, activityLog: [...existing, entry].slice(-30) };
          }),
          updatedAt: new Date().toISOString()
        };
      })
    );
  };

  // Subscribes to the SSE stream for an already-started run (used by both
  // sendMessage's initial run and retryRun/continueRun's follow-up runs) so the
  // retry/continue affordances get the exact same live-progress UX as a fresh send.
  const subscribeToRun = (runId: string, finalThreadId: string, aiMsgId: string): Promise<void> => {
    return new Promise<void>((resolve) => {
      const controller = apiClient.chat.streamRunEvents(
        runId,
        (event: any) => {
          if (event.type === 'state') {
            const label = event.current_action || `Status: ${event.status}`;
            updateAiMessage(finalThreadId, aiMsgId, { statusText: label });
            appendActivityStep(finalThreadId, aiMsgId, { label, source: 'agent', status: 'running' });
          } else if (event.type === 'timing' && event.event?.tool) {
            const rawTool = event.event.tool as string;
            const durationMs = event.event.duration_ms;
            const label = friendlyToolLabel(rawTool);
            updateAiMessage(finalThreadId, aiMsgId, { statusText: `${label} (${durationMs}ms)` });
            appendActivityStep(finalThreadId, aiMsgId, {
              label,
              source: rawTool,
              status: 'done',
              durationMs
            });
          } else if (event.type === 'completed') {
            const finalText = event.reply || 'Response received from AI server.';
            const status: string | undefined = event.status;
            const badge = STATUS_BADGES[status || ''] || (event.error && status !== 'COMPLETED' ? '⚠️ ' : '');
            updateAiMessage(finalThreadId, aiMsgId, {
              text: `${badge}${finalText}`,
              toolResults: event.tool_results,
              statusText: undefined,
              isStreaming: false,
              completionStatus: status,
              verifiedCount: event.verified_count ?? undefined,
              requestedCount: event.requested_count ?? undefined,
            });
            appendActivityStep(finalThreadId, aiMsgId, {
              label: status === 'COMPLETED' ? '✅ Completed' : `${badge}${status || 'Finished'}`,
              source: 'agent',
              status: status && status !== 'COMPLETED' && status !== 'PARTIAL' ? 'error' : 'done'
            });
            activeStreamRef.current = null;
            resolve();
          } else if (event.type === 'error') {
            updateAiMessage(finalThreadId, aiMsgId, {
              text: `⚠️ ${event.message || 'Agent stream error.'}`,
              statusText: undefined,
              isStreaming: false
            });
            activeStreamRef.current = null;
            resolve();
          }
        },
        () => {
          apiClient.chat.getRunStatus(runId)
            .then((status: any) => {
              updateAiMessage(finalThreadId, aiMsgId, {
                text: status.reply || '⚠️ Lost connection to the live agent stream, and no final reply was recorded.',
                toolResults: status.toolCalls,
                statusText: undefined,
                isStreaming: false
              });
            })
            .catch(() => {
              updateAiMessage(finalThreadId, aiMsgId, {
                text: '⚠️ Lost connection to the live agent stream and could not recover the final result.',
                statusText: undefined,
                isStreaming: false
              });
            })
            .finally(() => resolve());
        }
      );
      activeStreamRef.current = { controller, runId, threadId: finalThreadId, aiMsgId };
    });
  };

  // Retries a FAILED/TIMEOUT/NO_RESULTS/CANCELLED run (the [Retry] button) by
  // starting a brand-new backend run with the same prompt, then live-streaming
  // its progress into a fresh placeholder AI message — same UX as a normal send.
  const retryRun = async (threadId: string, failedRunId: string) => {
    setIsGenerating(true);
    const aiMsgId = `msg-ai-${Date.now()}`;
    const placeholderMsg: Message = {
      id: aiMsgId,
      sender: 'ai',
      text: '',
      statusText: 'Retrying…',
      activityLog: [],
      isStreaming: true,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setChats(prev =>
      prev.map(c =>
        c.id === threadId
          ? { ...c, messages: [...c.messages, placeholderMsg], updatedAt: new Date().toISOString() }
          : c
      )
    );
    try {
      const startRes = await apiClient.chat.retryRun(failedRunId);
      const runId: string = startRes.runId || startRes.run_id;
      updateAiMessage(threadId, aiMsgId, { runId });
      await subscribeToRun(runId, threadId, aiMsgId);
    } catch (err: any) {
      updateAiMessage(threadId, aiMsgId, {
        text: `⚠️ Could not retry: ${err.message || 'Unknown error.'}`,
        statusText: undefined,
        isStreaming: false
      });
    } finally {
      activeStreamRef.current = null;
      setIsGenerating(false);
    }
  };

  // Resumes a WAITING_FOR_USER run (the [Continue] button) — e.g. after the user
  // has completed a required login inside the connected browser window.
  const continueRun = async (threadId: string, waitingRunId: string) => {
    setIsGenerating(true);
    const aiMsgId = `msg-ai-${Date.now()}`;
    const placeholderMsg: Message = {
      id: aiMsgId,
      sender: 'ai',
      text: '',
      statusText: 'Resuming…',
      activityLog: [],
      isStreaming: true,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setChats(prev =>
      prev.map(c =>
        c.id === threadId
          ? { ...c, messages: [...c.messages, placeholderMsg], updatedAt: new Date().toISOString() }
          : c
      )
    );
    try {
      const startRes = await apiClient.chat.continueRun(waitingRunId);
      const runId: string = startRes.runId || startRes.run_id;
      updateAiMessage(threadId, aiMsgId, { runId });
      await subscribeToRun(runId, threadId, aiMsgId);
    } catch (err: any) {
      updateAiMessage(threadId, aiMsgId, {
        text: `⚠️ Could not continue: ${err.message || 'Unknown error.'}`,
        statusText: undefined,
        isStreaming: false
      });
    } finally {
      activeStreamRef.current = null;
      setIsGenerating(false);
    }
  };

  const sendMessage = async (text: string, attachedFile?: File | null) => {
    if (!text.trim() && !attachedFile) return;

    let currentThreadId = activeChatId;

    const userMessageText = attachedFile
      ? `${text} \n[📎 Attached file: ${attachedFile.name}]`
      : text;

    const newMsg: Message = {
      id: `msg-${Date.now()}`,
      sender: 'user',
      text: userMessageText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    if (!currentThreadId) {
      const newThread: ChatThread = {
        id: `chat-${Date.now()}`,
        title: text.slice(0, 24) || 'New Conversation',
        category: 'favorites',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        activePluginIds: [...activePluginIds],
        messages: [newMsg]
      };
      setChats(prev => [newThread, ...prev]);
      setActiveChatId(newThread.id);
      currentThreadId = newThread.id;
    } else {
      setChats(prev =>
        prev.map(c =>
          c.id === currentThreadId
            ? { ...c, messages: [...c.messages, newMsg], updatedAt: new Date().toISOString() }
            : c
        )
      );
    }

    setIsGenerating(true);

    // Placeholder AI message shown immediately, live-updated as SSE progress events arrive.
    const aiMsgId = `msg-ai-${Date.now()}`;
    const placeholderMsg: Message = {
      id: aiMsgId,
      sender: 'ai',
      text: '',
      statusText: 'Queued…',
      activityLog: [],
      isStreaming: true,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setChats(prev =>
      prev.map(c =>
        c.id === currentThreadId
          ? { ...c, messages: [...c.messages, placeholderMsg], updatedAt: new Date().toISOString() }
          : c
      )
    );

    try {
      let documentIds: string[] | undefined = undefined;

      if (attachedFile) {
        try {
          const docRes = await apiClient.documents.upload(attachedFile);
          if (docRes.document?.id) {
            documentIds = [docRes.document.id];
          }
        } catch (docErr) {
          console.warn('Document upload error:', docErr);
        }
      }

      // 1. Kick off the run asynchronously — returns immediately with runId/threadId (HTTP 202).
      const startRes = await apiClient.chat.sendMessageAsync({
        message: text || `Summarize attached document ${attachedFile?.name || ''}`,
        threadId: currentThreadId,
        model: appConfig.ai.defaultModel ? appConfig.ai.defaultModel : undefined,
        activePlugins: activePluginIds,
        documentIds
      });

      const runId: string = startRes.runId;
      const finalThreadId: string = startRes.threadId || currentThreadId;

      // Ensure the thread ID in the chats list and activeChatId stay in sync with the backend DB ID
      if (currentThreadId !== finalThreadId) {
        setChats(prev =>
          prev.map(c =>
            c.id === currentThreadId
              ? { ...c, id: finalThreadId }
              : c
          )
        );
        setActiveChatId(finalThreadId);
        currentThreadId = finalThreadId;
      }

      updateAiMessage(finalThreadId, aiMsgId, { runId });

      // 2. Subscribe to the live SSE progress stream for this exact run.
      await subscribeToRun(runId, finalThreadId, aiMsgId);
    } catch (err: any) {
      console.warn('API communication error:', err);
      const errMsg = err.message || '';
      const isDown = errMsg.includes('Failed to fetch') || errMsg.includes('NetworkError') || errMsg.includes('ECONNREFUSED') || errMsg.includes('not reachable') || errMsg.includes('502') || errMsg.includes('503');

      const friendlyText = isDown
        ? `⚠️ **Oops! Backend Server Not Found.**\n\nUnable to establish a connection with the backend server at \`${appConfig.backend.endpointUrl || 'http://localhost:8000'}\`.\n\nPlease check that the backend service is running and try again.`
        : `⚠️ **Oops! Something went wrong.**\n\n${errMsg || 'Unable to process your request at this time. Please try again.'}`;

      updateAiMessage(currentThreadId!, aiMsgId, { text: friendlyText, statusText: undefined, isStreaming: false });
    } finally {
      activeStreamRef.current = null;
      setIsGenerating(false);
    }
  };

  return (
    <ChatContext.Provider
      value={{
        theme,
        toggleTheme,
        appConfig,
        updateAppConfig,
        resetAppConfig,
        userSession,
        loginUser,
        logoutUser,
        chats,
        activeChatId,
        activeChat,
        setActiveChatId: handleSetActiveChatId,
        selectChat,
        isConversationsLoading,
        isLoadingMessages,
        createNewChat,
        deleteChat,
        clearAllChats,
        loadConversations,
        searchQuery,
        setSearchQuery,
        selectedCategory,
        setSelectedCategory,
        plugins,
        pluginCategories,
        togglePlugin,
        addCustomTool,
        deleteCustomTool,
        loadPlugins,
        activePluginIds,
        toggleActivePluginId,
        isGenerating,
        sendMessage,
        retryRun,
        continueRun,
        stopGenerating,
        sidebarOpen,
        setSidebarOpen,
        toggleSidebar,
        isPluginModalOpen,
        setIsPluginModalOpen,
        isPromptLibraryOpen,
        setIsPromptLibraryOpen,
        isCustomToolModalOpen,
        setIsCustomToolModalOpen,
        isUpgradeModalOpen,
        setIsUpgradeModalOpen,
        isSettingsModalOpen,
        setIsSettingsModalOpen,
        isAuthModalOpen,
        setIsAuthModalOpen,
        isBrowserModalOpen,
        setIsBrowserModalOpen,
        activeConfirmation,
        setActiveConfirmation,
        browserStatus,
        refreshBrowserStatus,
        resolveBrowserConfirmation
      }}
    >
      {children}
    </ChatContext.Provider>
  );
};

export const useChatContext = () => {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChatContext must be used within ChatProvider');
  return ctx;
};

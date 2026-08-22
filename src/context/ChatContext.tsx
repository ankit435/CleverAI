import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { Theme, ChatThread, Plugin, PluginCategoryInfo, ChatCategory, Message, CustomToolFormData } from '../types';
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

  // Load isolated user conversations from PostgreSQL backend
  const loadConversations = useCallback(async (targetUserId?: string | number) => {
    const token = localStorage.getItem('clever_jwt_token');
    if (!token) {
      setChats([]);
      setActiveChatId(null);
      return;
    }

    try {
      const res = await apiClient.conversations.list({ limit: 50 });
      if (res && Array.isArray(res.conversations)) {
        const loadedThreads: ChatThread[] = await Promise.all(
          res.conversations.map(async (c: any) => {
            try {
              const detail = await apiClient.conversations.get(c.id);
              const msgs: Message[] = (detail.conversation?.messages || []).map((m: any) => ({
                id: m.id,
                sender: m.sender,
                text: m.text,
                timestamp: new Date(m.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                toolResults: m.metadata?.toolResults,
                isStreaming: false
              }));
              return {
                id: c.id,
                title: c.title,
                category: (c.category as ChatCategory) || 'favorites',
                createdAt: c.createdAt,
                updatedAt: c.updatedAt,
                activePluginIds: ['web-search', 'code-interpreter', 'dalle3-image'],
                messages: msgs
              };
            } catch {
              return {
                id: c.id,
                title: c.title,
                category: (c.category as ChatCategory) || 'favorites',
                createdAt: c.createdAt,
                updatedAt: c.updatedAt,
                activePluginIds: ['web-search', 'code-interpreter', 'dalle3-image'],
                messages: []
              };
            }
          })
        );
        setChats(loadedThreads);
        const uid = targetUserId || userSession.id;
        if (uid) {
          localStorage.setItem(`clever_chats_${uid}`, JSON.stringify(loadedThreads));
        }
      }
    } catch (err) {
      console.warn('Load user conversations note:', err);
    }
  }, [userSession.id]);

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

  // Message Sending via Central apiClient
  const [isGenerating, setIsGenerating] = useState(false);

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

      const data = await apiClient.chat.sendMessage({
        message: text || `Summarize attached document ${attachedFile?.name || ''}`,
        threadId: currentThreadId,
        model: appConfig.ai.defaultModel ? appConfig.ai.defaultModel : undefined,
        activePlugins: activePluginIds,
        documentIds
      });

      const aiMsg: Message = {
        id: `msg-ai-${Date.now()}`,
        sender: 'ai',
        text: data.reply || 'Response received from AI server.',
        toolResults: data.toolResults,
        isStreaming: true,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      const finalThreadId = data.threadId || currentThreadId;
      if (currentThreadId !== finalThreadId) {
        setActiveChatId(finalThreadId);
      }

      setChats(prev =>
        prev.map(c =>
          c.id === currentThreadId
            ? { ...c, id: finalThreadId, messages: [...c.messages, aiMsg], updatedAt: new Date().toISOString() }
            : c
        )
      );
    } catch (err: any) {
      console.warn('API communication error:', err);
      const errMsg = err.message || '';
      const isDown = errMsg.includes('Failed to fetch') || errMsg.includes('NetworkError') || errMsg.includes('ECONNREFUSED') || errMsg.includes('not reachable') || errMsg.includes('502') || errMsg.includes('503');

      const friendlyText = isDown
        ? `⚠️ **Oops! Backend Server Not Found.**\n\nUnable to establish a connection with the backend server at \`${appConfig.backend.endpointUrl || 'http://localhost:8000'}\`.\n\nPlease check that the backend service is running and try again.`
        : `⚠️ **Oops! Something went wrong.**\n\n${errMsg || 'Unable to process your request at this time. Please try again.'}`;

      const errorAiMsg: Message = {
        id: `msg-ai-err-${Date.now()}`,
        sender: 'ai',
        text: friendlyText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setChats(prev =>
        prev.map(c =>
          c.id === currentThreadId
            ? { ...c, messages: [...c.messages, errorAiMsg], updatedAt: new Date().toISOString() }
            : c
        )
      );
    } finally {
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
        setActiveChatId,
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

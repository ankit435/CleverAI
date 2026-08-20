import React, { createContext, useContext, useState, useEffect } from 'react';
import { Theme, ChatThread, Plugin, ChatCategory, Message, CustomToolFormData } from '../types';
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
  deleteChat: (id: string) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  selectedCategory: ChatCategory | 'all';
  setSelectedCategory: (cat: ChatCategory | 'all') => void;
  plugins: Plugin[];
  togglePlugin: (id: string) => void;
  addCustomTool: (data: CustomToolFormData) => void;
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
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

const INITIAL_CHATS: ChatThread[] = [
  {
    id: 'chat-1',
    title: 'React Dashboard UI',
    category: 'code',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    activePluginIds: ['code-interpreter', 'web-search'],
    messages: [
      {
        id: 'm1',
        sender: 'user',
        text: 'How can I build a responsive dashboard layout with Vite and React?',
        timestamp: '10:14 AM'
      },
      {
        id: 'm2',
        sender: 'ai',
        text: "Here is a complete modern dashboard component setup using React, CSS Grid, and custom design tokens. You can structure your layout with a collapsible sidebar and flexible main viewport container.",
        timestamp: '10:14 AM'
      }
    ]
  }
];

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Config state
  const [appConfig, setAppConfig] = useState<AppConfig>(() => {
    const saved = localStorage.getItem('clever_app_config');
    return saved ? JSON.parse(saved) : DEFAULT_APP_CONFIG;
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

  // User Session State: isLoggedIn is TRUE ONLY IF a valid token exists in localStorage
  const [userSession, setUserSession] = useState<UserSession>(() => {
    const savedToken = localStorage.getItem('clever_jwt_token');
    const savedUser = localStorage.getItem('clever_auth_user');
    if (savedToken && savedUser) {
      try {
        const parsed = JSON.parse(savedUser);
        if (parsed.name && !parsed.name.toLowerCase().includes('guest')) {
          return { ...parsed, isLoggedIn: true, token: savedToken };
        }
      } catch (e) {
        // Fallback
      }
    }
    return {
      name: appConfig.userProfile.name || 'Ankit',
      email: appConfig.userProfile.email || 'ankitkumar700413@gmail.com',
      avatarUrl: appConfig.userProfile.avatarUrl,
      plan: appConfig.userProfile.plan || 'Free',
      isLoggedIn: Boolean(savedToken)
    };
  });

  // Verify session on app load via central apiClient.auth.me()
  useEffect(() => {
    const token = localStorage.getItem('clever_jwt_token');

    if (!token) {
      setUserSession(prev => ({ ...prev, isLoggedIn: false }));
      setIsAuthModalOpen(true);
      return;
    }

    apiClient.auth.me()
      .then(data => {
        if (data.user) {
          const verifiedSession: UserSession = {
            id: data.user.id,
            name: data.user.name || 'Ankit',
            email: data.user.email || 'ankitkumar700413@gmail.com',
            avatarUrl: data.user.avatarUrl || appConfig.userProfile.avatarUrl,
            plan: data.user.plan || 'Free',
            isLoggedIn: true,
            token,
            lastLoginAt: new Date().toISOString()
          };
          setUserSession(verifiedSession);
          localStorage.setItem('clever_auth_user', JSON.stringify(verifiedSession));
        }
      })
      .catch(() => {
        localStorage.removeItem('clever_jwt_token');
        localStorage.removeItem('clever_auth_user');
        setUserSession(prev => ({ ...prev, isLoggedIn: false }));
        setIsAuthModalOpen(true);
      });
  }, []);

  const loginUser = (token: string, user: Partial<UserSession>) => {
    localStorage.setItem('clever_jwt_token', token);
    const newSession: UserSession = {
      id: user.id,
      name: user.name || 'Ankit',
      email: user.email || 'ankitkumar700413@gmail.com',
      avatarUrl: user.avatarUrl || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&q=80',
      plan: user.plan || 'Free',
      isLoggedIn: true,
      token,
      lastLoginAt: new Date().toISOString()
    };
    localStorage.setItem('clever_auth_user', JSON.stringify(newSession));
    setUserSession(newSession);
    setIsAuthModalOpen(false);
    updateAppConfig({
      ...appConfig,
      userProfile: {
        ...appConfig.userProfile,
        name: newSession.name,
        email: newSession.email,
        avatarUrl: newSession.avatarUrl,
        plan: newSession.plan
      }
    });
  };

  const logoutUser = () => {
    localStorage.removeItem('clever_jwt_token');
    localStorage.removeItem('clever_auth_user');
    const loggedOutState: UserSession = {
      name: 'Ankit',
      email: 'ankitkumar700413@gmail.com',
      avatarUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=120&q=80',
      plan: 'Free',
      isLoggedIn: false
    };
    setUserSession(loggedOutState);
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

  // Chats & Filters state
  const [chats, setChats] = useState<ChatThread[]>(() => {
    const saved = localStorage.getItem('clever_chats');
    return saved ? JSON.parse(saved) : INITIAL_CHATS;
  });

  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<ChatCategory | 'all'>('all');

  useEffect(() => {
    localStorage.setItem('clever_chats', JSON.stringify(chats));
  }, [chats]);

  const activeChat = chats.find(c => c.id === activeChatId) || null;

  // Plugins state
  const [plugins, setPlugins] = useState<Plugin[]>(() => {
    const saved = localStorage.getItem('clever_plugins');
    return saved ? JSON.parse(saved) : INITIAL_PLUGINS;
  });

  useEffect(() => {
    localStorage.setItem('clever_plugins', JSON.stringify(plugins));
  }, [plugins]);

  const [activePluginIds, setActivePluginIds] = useState<string[]>(['web-search', 'code-interpreter', 'dalle3-image']);

  const togglePlugin = (id: string) => {
    setPlugins(prev =>
      prev.map(p => (p.id === id ? { ...p, enabled: !p.enabled } : p))
    );
  };

  const toggleActivePluginId = (id: string) => {
    setActivePluginIds(prev =>
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    );
  };

  const addCustomTool = (data: CustomToolFormData) => {
    const newTool: Plugin = {
      id: `custom-${Date.now()}`,
      name: data.name,
      description: data.description,
      icon: data.icon || '⚡',
      category: 'custom',
      enabled: true,
      isCustom: true,
      author: 'User Defined',
      version: '1.0.0',
      endpointUrl: data.endpointUrl,
      method: data.method
    };
    setPlugins(prev => [...prev, newTool]);
    setActivePluginIds(prev => [...prev, newTool.id]);
    setIsCustomToolModalOpen(false);
  };

  const createNewChat = () => {
    setActiveChatId(null);
    setSidebarOpen(false);
  };

  const deleteChat = (id: string) => {
    setChats(prev => prev.filter(c => c.id !== id));
    if (activeChatId === id) setActiveChatId(null);
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
      const data = await apiClient.chat.sendMessage({
        message: text,
        threadId: currentThreadId,
        model: appConfig.ai.defaultModel,
        activePlugins: activePluginIds
      });

      const aiMsg: Message = {
        id: `msg-ai-${Date.now()}`,
        sender: 'ai',
        text: data.reply || 'Response received from AI server.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setChats(prev =>
        prev.map(c =>
          c.id === currentThreadId
            ? { ...c, messages: [...c.messages, aiMsg], updatedAt: new Date().toISOString() }
            : c
        )
      );
    } catch (err: any) {
      console.warn('API fetch note:', err);
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
        searchQuery,
        setSearchQuery,
        selectedCategory,
        setSelectedCategory,
        plugins,
        togglePlugin,
        addCustomTool,
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
        setIsAuthModalOpen
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

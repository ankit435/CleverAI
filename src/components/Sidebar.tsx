import React, { useState } from 'react';
import { useChatContext } from '../context/ChatContext';
import { CATEGORIES } from '../data/defaultPlugins';
import { apiClient } from '../config/apiClient';
import { 
  MessageSquare, 
  Folder, 
  LayoutGrid, 
  FileText, 
  Clock, 
  Search, 
  Plus, 
  Zap, 
  X,
  SlidersHorizontal, 
  Settings, 
  LogOut, 
  LogIn, 
  Trash2,
  Edit3,
  Check,
  Download
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  const {
    appConfig,
    userSession,
    logoutUser,
    chats,
    activeChatId,
    setActiveChatId,
    createNewChat,
    deleteChat,
    clearAllChats,
    searchQuery,
    setSearchQuery,
    selectedCategory,
    setSelectedCategory,
    sidebarOpen,
    setSidebarOpen,
    setIsPluginModalOpen,
    setIsUpgradeModalOpen,
    setIsSettingsModalOpen,
    setIsAuthModalOpen
  } = useChatContext();

  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  const filteredChats = chats.filter(c => {
    const matchesSearch = c.title.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCat = selectedCategory === 'all' || c.category === selectedCategory;
    return matchesSearch && matchesCat;
  });

  const handleStartRename = (c: { id: string; title: string }, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingChatId(c.id);
    setEditTitle(c.title);
  };

  const handleSaveRename = async (id: string, e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!editTitle.trim()) {
      setEditingChatId(null);
      return;
    }

    try {
      await apiClient.conversations.update(id, { title: editTitle.trim() });
      const target = chats.find(c => c.id === id);
      if (target) {
        target.title = editTitle.trim();
      }
    } catch (err) {
      console.warn('Rename chat error:', err);
    }
    setEditingChatId(null);
  };

  const handleExportFullChat = (chat: any, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const markdownLines = [
        `# ${chat.title}`,
        `*Created: ${new Date(chat.createdAt).toLocaleString()}*`,
        '',
        '---',
        ''
      ];

      (chat.messages || []).forEach((m: any) => {
        const senderLabel = m.sender === 'user' ? (userSession.name || 'User') : `${appConfig.branding.appName} AI`;
        markdownLines.push(`### 👤 ${senderLabel} (${m.timestamp || ''})`);
        markdownLines.push(m.text || '');
        markdownLines.push('');
      });

      const fullMarkdown = markdownLines.join('\n');
      const blob = new Blob([fullMarkdown], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${chat.title.replace(/[^a-zA-Z0-9_-]/g, '_')}.md`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.warn('Export chat error:', err);
    }
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />
      )}

      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        {/* Top Logo & App Title */}
        <div className="sidebar-logo">
          <div className="logo-badge">
            <Zap size={18} fill="currentColor" />
          </div>
          <span className="logo-text">{appConfig.branding.appName}</span>

          {/* Close button for mobile */}
          <button 
            className="mobile-menu-btn" 
            style={{ marginLeft: 'auto' }}
            onClick={() => setSidebarOpen(false)}
          >
            <X size={20} />
          </button>
        </div>

        {/* Search Bar with Shortcut Keyboard Badge */}
        <div className="sidebar-search">
          <div className="search-input-wrapper">
            <Search size={15} />
            <input
              type="text"
              placeholder="Search"
              className="search-input"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
            <span className="shortcut-kbd">⌥F</span>
          </div>
        </div>

        {/* Main Navigation Items */}
        <nav className="sidebar-nav">
          <button 
            className={`nav-item ${selectedCategory === 'all' && !activeChatId ? 'active' : ''}`}
            onClick={() => {
              setSelectedCategory('all');
              createNewChat();
            }}
          >
            <MessageSquare size={17} />
            <span>Chats</span>
          </button>

          <button className="nav-item" onClick={() => setIsPluginModalOpen(true)}>
            <SlidersHorizontal size={17} />
            <span>Plugins & Tools</span>
          </button>

          <button className="nav-item">
            <Folder size={17} />
            <span>Projects</span>
          </button>

          <button className="nav-item">
            <LayoutGrid size={17} />
            <span>Templates</span>
          </button>

          <button className="nav-item">
            <FileText size={17} />
            <span>Documents</span>
          </button>

          <button className="nav-item">
            <Clock size={17} />
            <span>History</span>
          </button>
        </nav>

        {/* CHAT LIST Section Header & Color Categories */}
        <div className="sidebar-section">
          <div className="section-title">CHAT LIST</div>

          {CATEGORIES.map(cat => {
            const count = chats.filter(c => c.category === cat.id).length;
            return (
              <button
                key={cat.id}
                className={`category-item ${selectedCategory === cat.id ? 'active' : ''}`}
                onClick={() => setSelectedCategory(selectedCategory === cat.id ? 'all' : cat.id)}
              >
                <span className="category-dot" style={{ backgroundColor: cat.color }} />
                <span style={{ flex: 1 }}>{cat.label}</span>
                {count > 0 && <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{count}</span>}
              </button>
            );
          })}

          <button className="category-item" style={{ color: 'var(--text-muted)', marginTop: '4px' }}>
            <Plus size={14} />
            <span>New list</span>
          </button>

          {/* Active Chat History Items */}
          {filteredChats.length > 0 && (
            <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 12px' }}>
                <span className="section-title" style={{ fontSize: '10px', padding: 0, margin: 0 }}>RECENTS</span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (window.confirm('Are you sure you want to delete all chat history? This cannot be undone.')) {
                      clearAllChats();
                    }
                  }}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    fontSize: '10px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '2px 4px',
                    borderRadius: '4px'
                  }}
                  title="Clear all chat history from database"
                >
                  <Trash2 size={11} />
                  <span>Clear all</span>
                </button>
              </div>

              {filteredChats.map(c => (
                <div
                  key={c.id}
                  className={`nav-item ${activeChatId === c.id ? 'active' : ''}`}
                  onClick={() => {
                    if (editingChatId === c.id) return;
                    setActiveChatId(c.id);
                    setSidebarOpen(false);
                  }}
                  style={{ fontSize: '13px', padding: '7px 10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
                >
                  {editingChatId === c.id ? (
                    <form onSubmit={(e) => handleSaveRename(c.id, e)} style={{ display: 'flex', alignItems: 'center', flex: 1, gap: '4px' }}>
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onBlur={() => handleSaveRename(c.id)}
                        autoFocus
                        style={{
                          flex: 1,
                          fontSize: '12px',
                          padding: '2px 6px',
                          background: 'var(--bg-app)',
                          border: '1px solid var(--primary)',
                          borderRadius: '4px',
                          color: 'var(--text-main)'
                        }}
                      />
                      <button
                        type="submit"
                        style={{ background: 'none', border: 'none', color: '#10b981', cursor: 'pointer', display: 'flex' }}
                      >
                        <Check size={13} />
                      </button>
                    </form>
                  ) : (
                    <>
                      <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginRight: '6px' }}>
                        {c.title}
                      </span>
                      
                      <div style={{ display: 'flex', alignItems: 'center', gap: '2px', opacity: 0.8 }}>
                        <button
                          type="button"
                          onClick={(e) => handleStartRename(c, e)}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: 'var(--text-muted)',
                            cursor: 'pointer',
                            padding: '2px',
                            borderRadius: '3px',
                            display: 'flex'
                          }}
                          title="Rename title"
                        >
                          <Edit3 size={12} />
                        </button>

                        <button
                          type="button"
                          onClick={(e) => handleExportFullChat(c, e)}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: 'var(--text-muted)',
                            cursor: 'pointer',
                            padding: '2px',
                            borderRadius: '3px',
                            display: 'flex'
                          }}
                          title="Export chat (.md)"
                        >
                          <Download size={12} />
                        </button>

                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            deleteChat(c.id);
                          }}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: 'var(--text-muted)',
                            cursor: 'pointer',
                            padding: '2px',
                            borderRadius: '3px',
                            display: 'flex'
                          }}
                          title="Delete this chat"
                        >
                          <Trash2 size={12} style={{ color: '#ef4444' }} />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer User Profile & Upgrade Section */}
        <div className="sidebar-footer">
          <div 
            className="user-card" 
            onClick={() => setIsAuthModalOpen(true)} 
            style={{ cursor: 'pointer', position: 'relative' }} 
            title="Click to Manage Account / Session"
          >
            <div style={{ position: 'relative' }}>
              {userSession.avatarUrl ? (
                <img
                  src={userSession.avatarUrl}
                  alt={userSession.name || 'User'}
                  className="user-avatar"
                />
              ) : (
                <div className="user-avatar" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'var(--primary)', color: '#fff', fontWeight: 700, fontSize: '13px', borderRadius: '50%' }}>
                  {(userSession.name || userSession.email || 'U').slice(0, 1).toUpperCase()}
                </div>
              )}
              {userSession.isLoggedIn && (
                <span
                  style={{
                    position: 'absolute',
                    bottom: '0',
                    right: '0',
                    width: '10px',
                    height: '10px',
                    backgroundColor: '#10b981',
                    borderRadius: '50%',
                    border: '2px solid var(--bg-sidebar)'
                  }}
                  title="Session Active"
                />
              )}
            </div>

            <div className="user-info">
              <span className="user-name">{userSession.name || (userSession.isLoggedIn ? 'Authenticated User' : 'Guest')}</span>
              <span className="user-email">{userSession.email || (userSession.isLoggedIn ? '' : 'Not signed in')}</span>
            </div>
            <span className="free-pill">{userSession.plan || 'Free'}</span>
          </div>

          <div style={{ display: 'flex', gap: '6px' }}>
            <button className="upgrade-btn" style={{ flex: 1 }} onClick={() => setIsUpgradeModalOpen(true)}>
              Upgrade to Pro
            </button>
            <button className="btn-theme-toggle" onClick={() => setIsSettingsModalOpen(true)} title="Workspace Settings">
              <Settings size={16} />
            </button>
            {userSession.isLoggedIn ? (
              <button className="btn-theme-toggle" onClick={logoutUser} title="Log Out Session" style={{ color: '#ef4444' }}>
                <LogOut size={16} />
              </button>
            ) : (
              <button className="btn-theme-toggle" onClick={() => setIsAuthModalOpen(true)} title="Log In" style={{ color: 'var(--primary)' }}>
                <LogIn size={16} />
              </button>
            )}
          </div>
        </div>
      </aside>
    </>
  );
};

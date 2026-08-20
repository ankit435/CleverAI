import React from 'react';
import { useChatContext } from '../context/ChatContext';
import { CATEGORIES } from '../data/defaultPlugins';
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
  ChevronRight,
  Settings,
  LogOut,
  LogIn
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

  const filteredChats = chats.filter(c => {
    const matchesSearch = c.title.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCat = selectedCategory === 'all' || c.category === selectedCategory;
    return matchesSearch && matchesCat;
  });

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
              <div className="section-title" style={{ fontSize: '10px' }}>RECENTS</div>
              {filteredChats.slice(0, 5).map(c => (
                <button
                  key={c.id}
                  className={`nav-item ${activeChatId === c.id ? 'active' : ''}`}
                  onClick={() => {
                    setActiveChatId(c.id);
                    setSidebarOpen(false);
                  }}
                  style={{ fontSize: '13px', padding: '7px 10px' }}
                >
                  <span style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {c.title}
                  </span>
                  <ChevronRight size={14} style={{ opacity: 0.5 }} />
                </button>
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

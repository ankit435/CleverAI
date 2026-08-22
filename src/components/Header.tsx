import React from 'react';
import { useChatContext } from '../context/ChatContext';
import { Plus, Menu, Moon, Sun, SlidersHorizontal, Trash2, Compass } from 'lucide-react';

export const Header: React.FC = () => {
  const {
    theme,
    toggleTheme,
    activeChat,
    createNewChat,
    deleteChat,
    toggleSidebar,
    setIsPluginModalOpen,
    setIsBrowserModalOpen,
    browserStatus
  } = useChatContext();

  const handleDeleteActiveChat = () => {
    if (activeChat?.id) {
      if (window.confirm(`Delete conversation "${activeChat.title}"? This cannot be undone.`)) {
        deleteChat(activeChat.id);
      }
    }
  };

  return (
    <header className="main-header">
      <div className="header-title-container">
        <button className="mobile-menu-btn" onClick={toggleSidebar}>
          <Menu size={20} />
        </button>
        <h1 className="header-title">
          {activeChat ? activeChat.title : 'New chat'}
        </h1>
      </div>

      <div className="header-actions">
        {/* Browser AI Agent Controller Trigger */}
        <button 
          className="btn-theme-toggle" 
          onClick={() => setIsBrowserModalOpen(true)}
          title="Browser AI Agent — Connect & Control Existing Browser"
          style={{ position: 'relative' }}
        >
          <Compass size={18} style={{ color: '#06b6d4' }} />
          <span 
            style={{
              position: 'absolute',
              top: '6px',
              right: '6px',
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              backgroundColor: browserStatus?.connected ? '#10b981' : '#64748b',
              boxShadow: browserStatus?.connected ? '0 0 6px #10b981' : 'none'
            }} 
          />
        </button>

        {activeChat && (
          <button 
            className="btn-theme-toggle" 
            onClick={handleDeleteActiveChat}
            title="Delete this conversation from database"
            style={{ color: '#ef4444' }}
          >
            <Trash2 size={18} />
          </button>
        )}

        <button 
          className="btn-theme-toggle" 
          onClick={() => setIsPluginModalOpen(true)}
          title="Plugin Manager & Tools"
        >
          <SlidersHorizontal size={18} />
        </button>

        <button 
          className="btn-theme-toggle" 
          onClick={toggleTheme}
          title="Toggle Light/Dark Mode"
        >
          {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
        </button>

        <button className="btn-new-chat" onClick={createNewChat}>
          <Plus size={16} />
          <span>New chat</span>
        </button>
      </div>
    </header>
  );
};

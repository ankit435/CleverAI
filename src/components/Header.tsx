import React from 'react';
import { useChatContext } from '../context/ChatContext';
import { Plus, Menu, Moon, Sun, SlidersHorizontal, Trash2 } from 'lucide-react';

export const Header: React.FC = () => {
  const {
    theme,
    toggleTheme,
    activeChat,
    createNewChat,
    deleteChat,
    toggleSidebar,
    setIsPluginModalOpen
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

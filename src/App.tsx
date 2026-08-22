import React from 'react';
import { ChatProvider, useChatContext } from './context/ChatContext';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { ChatWelcome } from './components/ChatWelcome';
import { PromptInputCard } from './components/PromptInputCard';
import { QuickPrompts } from './components/QuickPrompts';
import { ChatFeed } from './components/ChatFeed';
import { PluginManagerModal } from './components/PluginManagerModal';
import { CustomToolModal } from './components/CustomToolModal';
import { PromptLibraryModal } from './components/PromptLibraryModal';
import { UpgradeModal } from './components/UpgradeModal';
import { SettingsModal } from './components/SettingsModal';
import { AuthModal } from './components/AuthModal';
import { BrowserControlPanelModal } from './components/BrowserControlPanelModal';
import { HumanConfirmationModal } from './components/HumanConfirmationModal';

const AppContent: React.FC = () => {
  const { 
    activeChat, 
    appConfig, 
    isBrowserModalOpen,
    setIsBrowserModalOpen,
    activeConfirmation,
    setActiveConfirmation,
    resolveBrowserConfirmation
  } = useChatContext();
  const hasMessages = activeChat && activeChat.messages.length > 0;

  return (
    <div className="app-viewport">
      {/* Left Navigation Sidebar */}
      <Sidebar />

      {/* Main Workspace Area */}
      <div className="main-content">
        <Header />

        {!hasMessages ? (
          /* Empty Chat Mode: Beautiful vertical stack matching design */
          <div className="empty-workspace-hero">
            <div className="hero-center-stack">
              <ChatWelcome />
              <PromptInputCard />
              <QuickPrompts />
              <span className="bottom-disclaimer">
                {appConfig.branding.appName} AI may produce inaccurate information about people, places, or facts.
              </span>
            </div>
          </div>
        ) : (
          /* Active Conversation Mode: Scrollable Chat Feed + Bottom Input Bar */
          <>
            <div className="workspace-feed-area">
              <div className="workspace-content-container">
                <ChatFeed />
              </div>
            </div>

            <div className="bottom-input-bar">
              <div className="bottom-input-container">
                <PromptInputCard />
                <span className="bottom-disclaimer">
                  {appConfig.branding.appName} AI may produce inaccurate information about people, places, or facts.
                </span>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Modals & Plugins System */}
      <PluginManagerModal />
      <CustomToolModal />
      <PromptLibraryModal />
      <UpgradeModal />
      <SettingsModal />
      <AuthModal />
      <BrowserControlPanelModal 
        isOpen={isBrowserModalOpen} 
        onClose={() => setIsBrowserModalOpen(false)} 
      />
      <HumanConfirmationModal 
        confirmation={activeConfirmation} 
        onConfirm={resolveBrowserConfirmation} 
        onClose={() => setActiveConfirmation(null)} 
      />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <ChatProvider>
      <AppContent />
    </ChatProvider>
  );
};

export default App;

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

const AppContent: React.FC = () => {
  const { activeChat, appConfig, userSession } = useChatContext();
  const hasMessages = activeChat && activeChat.messages.length > 0;

  // Protected Route Guard: If not logged in, force full-screen Login Screen!
  if (!userSession.isLoggedIn) {
    return (
      <div className="app-viewport">
        <AuthModal isProtectedGate={true} />
      </div>
    );
  }

  return (
    <div className="app-viewport">
      {/* Left Navigation Sidebar */}
      <Sidebar />

      {/* Main Workspace Area */}
      <div className="main-content">
        <Header />

        {!hasMessages ? (
          /* Empty Chat Mode: Tight, beautiful vertical stack matching reference design */
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

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

// ─── Error Boundary ──────────────────────────────────────────────────────────
// Catches JS errors anywhere in the component tree so a single failing widget
// never takes down the entire chat UI.
interface ErrorBoundaryState { hasError: boolean; error: Error | null }
class AppErrorBoundary extends React.Component<React.PropsWithChildren, ErrorBoundaryState> {
  constructor(props: React.PropsWithChildren) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Log without leaking stack traces to the console in production
    if (process.env.NODE_ENV !== 'production') {
      console.error('[AppErrorBoundary]', error, info.componentStack);
    }
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', height: '100vh', gap: '16px',
          fontFamily: 'system-ui, sans-serif', padding: '24px', textAlign: 'center'
        }}>
          <h2 style={{ fontSize: '1.4rem', margin: 0 }}>Something went wrong</h2>
          <p style={{ color: '#888', maxWidth: '480px' }}>
            An unexpected error occurred. Your conversations are safely stored.
          </p>
          <button
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
            style={{
              padding: '10px 24px', borderRadius: '8px', border: 'none',
              background: 'var(--primary, #6366f1)', color: '#fff', cursor: 'pointer', fontSize: '0.95rem'
            }}
          >
            Reload app
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
// ─────────────────────────────────────────────────────────────────────────────

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
    <AppErrorBoundary>
      <ChatProvider>
        <AppErrorBoundary>
          <AppContent />
        </AppErrorBoundary>
      </ChatProvider>
    </AppErrorBoundary>
  );
};

export default App;

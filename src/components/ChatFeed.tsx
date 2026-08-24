import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useChatContext } from '../context/ChatContext';
import { ToolWidget } from './ToolWidget';
import { TypewriterText } from './TypewriterText';
import { MarkdownRenderer } from './MarkdownRenderer';
import { 
  Sparkles, 
  User, 
  Bot, 
  Copy, 
  Check, 
  Volume2, 
  VolumeX, 
  RotateCcw, 
  ThumbsUp, 
  ThumbsDown, 
  Download 
} from 'lucide-react';

// Global Set to track messages that have already animated so historical chats never re-animate
const animatedMessageIds = new Set<string>();

export const ChatFeed: React.FC = () => {
  const { activeChat, isGenerating, isLoadingMessages, appConfig, userSession, sendMessage } = useChatContext();
  const bottomRef = useRef<HTMLDivElement>(null);
  const currentChatIdRef = useRef<string | null>(null);

  // When switching to a chat thread, register all existing messages as already animated
  useEffect(() => {
    if (activeChat && activeChat.id !== currentChatIdRef.current) {
      currentChatIdRef.current = activeChat.id;
      activeChat.messages.forEach(m => animatedMessageIds.add(m.id));
    }
  }, [activeChat?.id]);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, []);

  useEffect(() => {
    const scrollTimer = setTimeout(() => {
      scrollToBottom();
    }, 50);
    return () => clearTimeout(scrollTimer);
  }, [activeChat?.messages?.length, isGenerating, scrollToBottom]);

  if (isLoadingMessages) {
    return (
      <div className="chat-messages-container" style={{ padding: '24px 16px', maxWidth: '800px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* User Question Skeleton */}
        <div className="message-bubble" style={{ display: 'flex', gap: '12px', opacity: 0.9 }}>
          <div className="skeleton-box" style={{ width: '34px', height: '34px', borderRadius: '50%', flexShrink: 0 }} />
          <div className="message-content-wrapper" style={{ flex: 1, maxWidth: '65%' }}>
            <div className="skeleton-box" style={{ width: '110px', height: '13px', marginBottom: '8px' }} />
            <div className="skeleton-box" style={{ width: '100%', height: '38px', borderRadius: '12px' }} />
          </div>
        </div>

        {/* AI Answer Skeleton */}
        <div className="message-bubble" style={{ display: 'flex', gap: '12px', opacity: 0.95 }}>
          <div className="skeleton-box" style={{ width: '34px', height: '34px', borderRadius: '50%', flexShrink: 0 }} />
          <div className="message-content-wrapper" style={{ flex: 1, maxWidth: '85%' }}>
            <div className="skeleton-box" style={{ width: '150px', height: '13px', marginBottom: '10px' }} />
            <div className="skeleton-box" style={{ width: '96%', height: '16px', marginBottom: '8px' }} />
            <div className="skeleton-box" style={{ width: '90%', height: '16px', marginBottom: '8px' }} />
            <div className="skeleton-box" style={{ width: '75%', height: '16px', marginBottom: '14px' }} />
            <div className="skeleton-box" style={{ width: '40%', height: '32px', borderRadius: '8px' }} />
          </div>
        </div>

        {/* User Follow-up Skeleton */}
        <div className="message-bubble" style={{ display: 'flex', gap: '12px', opacity: 0.75 }}>
          <div className="skeleton-box" style={{ width: '34px', height: '34px', borderRadius: '50%', flexShrink: 0 }} />
          <div className="message-content-wrapper" style={{ flex: 1, maxWidth: '50%' }}>
            <div className="skeleton-box" style={{ width: '90px', height: '13px', marginBottom: '8px' }} />
            <div className="skeleton-box" style={{ width: '100%', height: '32px', borderRadius: '12px' }} />
          </div>
        </div>
      </div>
    );
  }

  if (!activeChat) return null;

  return (
    <div className="chat-messages-container">
      {activeChat.messages.map((msg, index) => {
        const shouldAnimate = msg.sender === 'ai' && Boolean(msg.isStreaming) && !animatedMessageIds.has(msg.id);

        return (
          <div key={msg.id} className="message-bubble">
            <div className={`message-avatar ${msg.sender}`}>
              {msg.sender === 'user' ? (
                userSession.avatarUrl ? (
                  <img
                    src={userSession.avatarUrl}
                    alt={userSession.name || 'User'}
                    style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }}
                  />
                ) : (
                  <User size={18} />
                )
              ) : (
                <Bot size={18} />
              )}
            </div>

            <div className="message-content-wrapper">
              <span className="message-sender-name">
                {msg.sender === 'user' ? (userSession.name || 'You') : `${appConfig.branding.appName} AI`} • {msg.timestamp}
              </span>

              {shouldAnimate ? (
                <TypewriterText
                  text={msg.text}
                  isStreaming={true}
                  onComplete={() => animatedMessageIds.add(msg.id)}
                  onCharacterTyped={scrollToBottom}
                />
              ) : msg.sender === 'ai' && msg.isStreaming && !msg.text ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary)', fontSize: '14px' }}>
                  <Sparkles size={16} className="animate-spin" />
                  <span>{msg.statusText || 'Working on it…'}</span>
                </div>
              ) : msg.sender === 'ai' ? (
                <div className="message-body">
                  <MarkdownRenderer content={msg.text} />
                </div>
              ) : (
                <div className="message-body">{msg.text}</div>
              )}

              {/* Render Tool Results if any */}
              {msg.toolResults && msg.toolResults.map((tool, idx) => (
                <ToolWidget key={idx} result={tool} />
              ))}

              {/* Interactive Action Toolbar for AI responses */}
              {msg.sender === 'ai' && !shouldAnimate && (
                <MessageActionBar
                  text={msg.text}
                  onRegenerate={() => {
                    // Find preceding user message
                    for (let i = index - 1; i >= 0; i--) {
                      if (activeChat.messages[i].sender === 'user') {
                        sendMessage(activeChat.messages[i].text);
                        break;
                      }
                    }
                  }}
                />
              )}
            </div>
          </div>
        );
      })}

      <div ref={bottomRef} />
    </div>
  );
};

interface MessageActionBarProps {
  text: string;
  onRegenerate: () => void;
}

const MessageActionBar: React.FC<MessageActionBarProps> = ({ text, onRegenerate }) => {
  const [copied, setCopied] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.warn('Copy failed:', err);
    }
  };

  const handleSpeak = () => {
    if (!('speechSynthesis' in window)) {
      alert('Text-to-speech is not supported in your browser.');
      return;
    }

    if (isSpeaking) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      return;
    }

    window.speechSynthesis.cancel();
    // Clean out markdown symbols for smooth audio reading
    const cleanText = text.replace(/[`*#_~[\]()]/g, '');
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    setIsSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  const handleDownloadMarkdown = () => {
    try {
      const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `response_${Date.now()}.md`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.warn('Download markdown failed:', err);
    }
  };

  return (
    <div className="message-action-toolbar">
      <button
        type="button"
        className="msg-action-btn"
        onClick={handleCopy}
        title="Copy response"
      >
        {copied ? <Check size={14} style={{ color: '#10b981' }} /> : <Copy size={14} />}
        <span>{copied ? 'Copied' : 'Copy'}</span>
      </button>

      <button
        type="button"
        className={`msg-action-btn ${isSpeaking ? 'active-audio' : ''}`}
        onClick={handleSpeak}
        title={isSpeaking ? 'Stop reading' : 'Read aloud'}
      >
        {isSpeaking ? <VolumeX size={14} style={{ color: '#ef4444' }} /> : <Volume2 size={14} />}
        <span>{isSpeaking ? 'Stop' : 'Listen'}</span>
      </button>

      <button
        type="button"
        className="msg-action-btn"
        onClick={onRegenerate}
        title="Regenerate response"
      >
        <RotateCcw size={14} />
        <span>Retry</span>
      </button>

      <button
        type="button"
        className="msg-action-btn"
        onClick={handleDownloadMarkdown}
        title="Export as Markdown (.md)"
      >
        <Download size={14} />
        <span>Export</span>
      </button>

      <div style={{ marginLeft: 'auto', display: 'flex', gap: '4px' }}>
        <button
          type="button"
          className={`msg-action-btn icon-only ${feedback === 'up' ? 'active-good' : ''}`}
          onClick={() => setFeedback(feedback === 'up' ? null : 'up')}
          title="Helpful"
        >
          <ThumbsUp size={13} style={feedback === 'up' ? { color: '#10b981', fill: '#10b981' } : {}} />
        </button>

        <button
          type="button"
          className={`msg-action-btn icon-only ${feedback === 'down' ? 'active-bad' : ''}`}
          onClick={() => setFeedback(feedback === 'down' ? null : 'down')}
          title="Not helpful"
        >
          <ThumbsDown size={13} style={feedback === 'down' ? { color: '#ef4444', fill: '#ef4444' } : {}} />
        </button>
      </div>
    </div>
  );
};

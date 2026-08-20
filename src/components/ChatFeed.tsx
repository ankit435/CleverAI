import React, { useRef, useEffect } from 'react';
import { useChatContext } from '../context/ChatContext';
import { ToolWidget } from './ToolWidget';
import { Sparkles, User, Bot } from 'lucide-react';

export const ChatFeed: React.FC = () => {
  const { activeChat, isGenerating, appConfig } = useChatContext();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeChat?.messages, isGenerating]);

  if (!activeChat) return null;

  return (
    <div className="chat-messages-container">
      {activeChat.messages.map(msg => (
        <div key={msg.id} className="message-bubble">
          <div className={`message-avatar ${msg.sender}`}>
            {msg.sender === 'user' ? <User size={18} /> : <Bot size={18} />}
          </div>

          <div className="message-content-wrapper">
            <span className="message-sender-name">
              {msg.sender === 'user' ? appConfig.userProfile.name : `${appConfig.branding.appName} AI`} • {msg.timestamp}
            </span>

            <div className="message-body">{msg.text}</div>

            {/* Render Tool Results if any */}
            {msg.toolResults && msg.toolResults.map((tool, idx) => (
              <ToolWidget key={idx} result={tool} />
            ))}
          </div>
        </div>
      ))}

      {/* Streaming / Tool Loading indicator */}
      {isGenerating && (
        <div className="message-bubble" style={{ opacity: 0.85 }}>
          <div className="message-avatar ai">
            <Bot size={18} />
          </div>
          <div className="message-content-wrapper">
            <span className="message-sender-name">{appConfig.branding.appName} AI</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary)', fontSize: '14px' }}>
              <Sparkles size={16} className="animate-spin" />
              <span>Orchestrating active plugin tools & generating response...</span>
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};

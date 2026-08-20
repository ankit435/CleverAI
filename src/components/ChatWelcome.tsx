import React from 'react';
import { useChatContext } from '../context/ChatContext';

export const ChatWelcome: React.FC = () => {
  const { appConfig } = useChatContext();

  return (
    <div className="hero-section">
      <h2 className="hero-title">
        Hello {appConfig.userProfile.name} <span className="wave-hand">👋</span>
      </h2>
      <p className="hero-subtitle">
        {appConfig.branding.tagline}
      </p>
    </div>
  );
};

import React, { useState, useEffect, useRef } from 'react';
import { MarkdownRenderer } from './MarkdownRenderer';

interface TypewriterTextProps {
  text: string;
  isStreaming?: boolean;
  onCharacterTyped?: () => void;
  onComplete?: () => void;
}

export const TypewriterText: React.FC<TypewriterTextProps> = ({
  text,
  isStreaming = false,
  onCharacterTyped,
  onComplete
}) => {
  const [displayedText, setDisplayedText] = useState(isStreaming ? '' : text);
  const [isTyping, setIsTyping] = useState(isStreaming);
  const indexRef = useRef(0);

  useEffect(() => {
    if (!isStreaming) {
      setDisplayedText(text);
      setIsTyping(false);
      return;
    }

    setDisplayedText('');
    setIsTyping(true);
    indexRef.current = 0;

    // Smooth adaptive typing speed:
    // Short texts: 1 character every 16ms (~60 chars/sec)
    // Medium texts: 2 characters every 14ms (~140 chars/sec)
    // Long texts: 4 characters every 10ms (~400 chars/sec)
    const stepSize = text.length > 600 ? 5 : text.length > 250 ? 2 : 1;
    const intervalMs = text.length > 600 ? 10 : text.length > 250 ? 12 : 16;

    const interval = setInterval(() => {
      indexRef.current += stepSize;
      if (indexRef.current >= text.length) {
        setDisplayedText(text);
        setIsTyping(false);
        clearInterval(interval);
        onComplete?.();
      } else {
        setDisplayedText(text.slice(0, indexRef.current));
        onCharacterTyped?.();
      }
    }, intervalMs);

    return () => clearInterval(interval);
  }, [text, isStreaming]);

  return (
    <div className="message-body">
      <MarkdownRenderer content={displayedText} isStreaming={isTyping} />
    </div>
  );
};

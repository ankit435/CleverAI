import React from 'react';
import { useChatContext } from '../context/ChatContext';
import { Image, Code, FileText, ClipboardList, Sparkles } from 'lucide-react';

export const QuickPrompts: React.FC = () => {
  const { sendMessage } = useChatContext();

  const prompts = [
    {
      icon: <Image size={15} style={{ color: '#ec4899' }} />,
      label: 'Create image',
      prompt: 'Create a high quality futuristic UI design mockup for an AI agent dashboard'
    },
    {
      icon: <Code size={15} style={{ color: '#3b82f6' }} />,
      label: 'Analyze code',
      prompt: 'Analyze this code snippet for potential performance bottlenecks and memory leaks'
    },
    {
      icon: <FileText size={15} style={{ color: '#10b981' }} />,
      label: 'Summarize text',
      prompt: 'Summarize key takeaways and executive summary from this document'
    },
    {
      icon: <ClipboardList size={15} style={{ color: '#f59e0b' }} />,
      label: 'Make a plan',
      prompt: 'Create a step-by-step 4-week roadmap to deploy a React TypeScript app'
    },
    {
      icon: <Sparkles size={15} style={{ color: '#8b5cf6' }} />,
      label: 'Surprise me',
      prompt: 'Show me an exciting demo of multi-tool AI plugin orchestration with code and web search!'
    }
  ];

  return (
    <div className="quick-prompts-container">
      <span className="quick-prompts-label">Choose a quick prompt</span>
      <div className="quick-chips-grid">
        {prompts.map((p, i) => (
          <button
            key={i}
            className="quick-chip"
            onClick={() => sendMessage(p.prompt)}
          >
            {p.icon}
            <span>{p.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

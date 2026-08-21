import React, { useState } from 'react';
import { useChatContext } from '../context/ChatContext';
import { PROMPT_TEMPLATES } from '../data/promptTemplates';
import { X, BookOpen, Search, ArrowRight } from 'lucide-react';

export const PromptLibraryModal: React.FC = () => {
  const { isPromptLibraryOpen, setIsPromptLibraryOpen, sendMessage } = useChatContext();
  const [search, setSearch] = useState('');

  if (!isPromptLibraryOpen) return null;

  const filtered = PROMPT_TEMPLATES.filter(
    t => t.title.toLowerCase().includes(search.toLowerCase()) || t.description.toLowerCase().includes(search.toLowerCase())
  );

  const handleSelect = (promptText: string) => {
    setIsPromptLibraryOpen(false);
    sendMessage(promptText);
  };

  return (
    <div className="modal-overlay" onClick={() => setIsPromptLibraryOpen(false)}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <BookOpen size={20} style={{ color: 'var(--primary)' }} />
            <h3 className="modal-title">Prompt Library</h3>
          </div>
          <button className="btn-icon-subtle" onClick={() => setIsPromptLibraryOpen(false)}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <div className="search-input-wrapper">
            <Search size={15} />
            <input
              type="text"
              placeholder="Search prompt templates..."
              className="search-input"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {filtered.map(t => (
              <div
                key={t.id}
                onClick={() => handleSelect(t.prompt)}
                style={{
                  padding: '14px',
                  borderRadius: '12px',
                  border: '1px solid var(--border-light)',
                  backgroundColor: 'var(--bg-card)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}
                className="plugin-card"
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '18px' }}>{t.icon}</span>
                    <span style={{ fontSize: '14px', fontWeight: 600 }}>{t.title}</span>
                    <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '12px', backgroundColor: 'var(--bg-hover)', color: 'var(--text-muted)' }}>
                      {t.category}
                    </span>
                  </div>
                  <p style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    {t.description}
                  </p>
                </div>
                <ArrowRight size={16} style={{ color: 'var(--primary)', flexShrink: 0 }} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

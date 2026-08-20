import React, { useState } from 'react';
import { useChatContext } from '../context/ChatContext';
import { X, Search, Plus, Puzzle, ShieldCheck } from 'lucide-react';

export const PluginManagerModal: React.FC = () => {
  const {
    isPluginModalOpen,
    setIsPluginModalOpen,
    plugins,
    togglePlugin,
    setIsCustomToolModalOpen
  } = useChatContext();

  const [search, setSearch] = useState('');

  if (!isPluginModalOpen) return null;

  const filteredPlugins = plugins.filter(
    p => p.name.toLowerCase().includes(search.toLowerCase()) || p.description.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="modal-overlay" onClick={() => setIsPluginModalOpen(false)}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Puzzle size={20} style={{ color: 'var(--primary)' }} />
            <h3 className="modal-title">Plugins & Tool Directory</h3>
          </div>
          <button className="btn-icon-subtle" onClick={() => setIsPluginModalOpen(false)}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <div className="search-input-wrapper" style={{ flex: 1 }}>
              <Search size={15} />
              <input
                type="text"
                placeholder="Search tools & integrations..."
                className="search-input"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>

            <button
              className="btn-new-chat"
              style={{ fontSize: '13px', padding: '8px 12px', whiteSpace: 'nowrap' }}
              onClick={() => {
                setIsPluginModalOpen(false);
                setIsCustomToolModalOpen(true);
              }}
            >
              <Plus size={15} />
              <span>Add Custom Tool</span>
            </button>
          </div>

          <div className="plugins-list">
            {filteredPlugins.map(p => (
              <div key={p.id} className="plugin-card">
                <div className="plugin-info">
                  <div className="plugin-icon-box">{p.icon}</div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span className="plugin-title">{p.name}</span>
                      {p.isCustom && (
                        <span style={{ fontSize: '10px', padding: '2px 6px', background: 'var(--primary-light)', color: 'var(--primary)', borderRadius: '4px', fontWeight: 700 }}>
                          CUSTOM
                        </span>
                      )}
                    </div>
                    <p className="plugin-desc">{p.description}</p>
                    <div style={{ display: 'flex', gap: '12px', fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      <span>By {p.author || 'Clever AI'}</span>
                      <span>• v{p.version || '1.0'}</span>
                    </div>
                  </div>
                </div>

                <label className="switch">
                  <input
                    type="checkbox"
                    checked={p.enabled}
                    onChange={() => togglePlugin(p.id)}
                  />
                  <span className="slider" />
                </label>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

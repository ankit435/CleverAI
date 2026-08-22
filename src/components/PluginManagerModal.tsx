import React, { useState } from 'react';
import { useChatContext } from '../context/ChatContext';
import { X, Search, Plus, Puzzle, CheckCircle2, AlertCircle, Trash2, RefreshCw } from 'lucide-react';

export const PluginManagerModal: React.FC = () => {
  const {
    isPluginModalOpen,
    setIsPluginModalOpen,
    plugins,
    pluginCategories,
    togglePlugin,
    deleteCustomTool,
    loadPlugins,
    setIsCustomToolModalOpen
  } = useChatContext();

  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [isRefreshing, setIsRefreshing] = useState(false);

  if (!isPluginModalOpen) return null;

  // Dynamically compute categories if not yet loaded from backend
  const existingCategories = Array.from(new Set(plugins.map(p => p.category)));
  const displayCategories = pluginCategories.length > 0
    ? pluginCategories
    : [
        { id: 'all', label: 'All Tools', color: '#6366f1' },
        ...existingCategories.map(c => ({
          id: c,
          label: c.charAt(0).toUpperCase() + c.slice(1),
          color: '#6366f1'
        }))
      ];

  const filteredPlugins = plugins.filter(p => {
    const matchesSearch =
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.description.toLowerCase().includes(search.toLowerCase());
    const matchesCat = selectedCategory === 'all' || p.category === selectedCategory;
    return matchesSearch && matchesCat;
  });

  const availableCount = plugins.filter(p => p.isAvailable !== false).length;

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadPlugins();
    setTimeout(() => setIsRefreshing(false), 400);
  };

  return (
    <div className="modal-overlay" onClick={() => setIsPluginModalOpen(false)}>
      <div className="modal-content" style={{ maxWidth: '680px' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Puzzle size={20} style={{ color: 'var(--primary)' }} />
            <div>
              <h3 className="modal-title" style={{ margin: 0 }}>Plugins & Tool Directory</h3>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                {availableCount} of {plugins.length} tools available and ready
              </span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              className="btn-icon-subtle"
              onClick={handleRefresh}
              title="Refresh plugin availability from backend"
            >
              <RefreshCw size={16} className={isRefreshing ? 'animate-spin' : ''} />
            </button>
            <button className="btn-icon-subtle" onClick={() => setIsPluginModalOpen(false)}>
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="modal-body">
          {/* Search & Add Custom Tool Bar */}
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <div className="search-input-wrapper" style={{ flex: 1 }}>
              <Search size={15} />
              <input
                type="text"
                placeholder="Search dynamic plugins & tools..."
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

          {/* Dynamic Category Tabs */}
          <div style={{ display: 'flex', gap: '6px', overflowX: 'auto', paddingBottom: '4px' }}>
            {displayCategories.map(cat => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                style={{
                  fontSize: '12px',
                  fontWeight: selectedCategory === cat.id ? 700 : 500,
                  padding: '5px 12px',
                  borderRadius: '9999px',
                  border: '1px solid',
                  borderColor: selectedCategory === cat.id ? 'var(--primary)' : 'var(--border-light)',
                  backgroundColor: selectedCategory === cat.id ? 'var(--primary-light)' : 'transparent',
                  color: selectedCategory === cat.id ? 'var(--primary)' : 'var(--text-secondary)',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  transition: 'all 0.15s ease'
                }}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Plugins List */}
          <div className="plugins-list" style={{ maxHeight: '420px', overflowY: 'auto' }}>
            {filteredPlugins.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--text-muted)', fontSize: '13.5px' }}>
                No plugins found matching your query.
              </div>
            ) : (
              filteredPlugins.map(p => {
                const isAvail = p.isAvailable !== false;
                return (
                  <div key={p.id} className="plugin-card">
                    <div className="plugin-info" style={{ flex: 1 }}>
                      <div className="plugin-icon-box">{p.icon}</div>
                      <div style={{ flex: 1, overflow: 'hidden' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <span className="plugin-title">{p.name}</span>
                          
                          {/* Live Availability Badge */}
                          <span
                            style={{
                              fontSize: '10.5px',
                              padding: '2px 8px',
                              borderRadius: '9999px',
                              fontWeight: 600,
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              backgroundColor: isAvail ? 'rgba(34, 197, 94, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                              color: isAvail ? '#16a34a' : '#ef4444'
                            }}
                            title={p.statusMessage || (isAvail ? 'Ready to execute' : 'Temporarily unavailable')}
                          >
                            {isAvail ? <CheckCircle2 size={10} /> : <AlertCircle size={10} />}
                            {isAvail ? 'Available' : 'Offline'}
                          </span>

                          {p.isCustom && (
                            <span
                              style={{
                                fontSize: '10px',
                                padding: '2px 6px',
                                background: 'var(--primary-light)',
                                color: 'var(--primary)',
                                borderRadius: '4px',
                                fontWeight: 700
                              }}
                            >
                              CUSTOM
                            </span>
                          )}
                        </div>

                        <p className="plugin-desc" style={{ marginTop: '2px' }}>{p.description}</p>
                        
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                          <span>Category: <strong>{p.category}</strong></span>
                          <span>• By {p.author || 'Clever AI'}</span>
                          <span>• v{p.version || '1.0'}</span>
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      {p.isCustom && (
                        <button
                          type="button"
                          onClick={() => {
                            if (window.confirm(`Delete custom tool "${p.name}"?`)) {
                              deleteCustomTool(p.id);
                            }
                          }}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: '#ef4444',
                            cursor: 'pointer',
                            padding: '4px',
                            borderRadius: '4px',
                            display: 'flex',
                            alignItems: 'center',
                            opacity: 0.8
                          }}
                          title="Delete this custom tool"
                        >
                          <Trash2 size={15} />
                        </button>
                      )}

                      <label className="switch" title={p.enabled ? 'Enabled' : 'Disabled'}>
                        <input
                          type="checkbox"
                          checked={p.enabled}
                          onChange={() => togglePlugin(p.id)}
                        />
                        <span className="slider" />
                      </label>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

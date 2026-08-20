import React, { useState } from 'react';
import { useChatContext } from '../context/ChatContext';
import { X, Settings, User, Cpu, Server, Save, RotateCcw } from 'lucide-react';

export const SettingsModal: React.FC = () => {
  const { isSettingsModalOpen, setIsSettingsModalOpen, appConfig, updateAppConfig, resetAppConfig } = useChatContext();
  const [activeTab, setActiveTab] = useState<'profile' | 'ai' | 'backend'>('profile');
  const [formData, setFormData] = useState(appConfig);

  if (!isSettingsModalOpen) return null;

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    updateAppConfig(formData);
    setIsSettingsModalOpen(false);
  };

  const handleReset = () => {
    resetAppConfig();
    setIsSettingsModalOpen(false);
  };

  return (
    <div className="modal-overlay" onClick={() => setIsSettingsModalOpen(false)}>
      <div className="modal-content" style={{ maxWidth: '640px' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Settings size={20} style={{ color: 'var(--primary)' }} />
            <h3 className="modal-title">Workspace Configuration</h3>
          </div>
          <button className="btn-icon-subtle" onClick={() => setIsSettingsModalOpen(false)}>
            <X size={18} />
          </button>
        </div>

        {/* Tab Selection Navigation */}
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border-light)', padding: '0 24px' }}>
          <button
            type="button"
            className={`nav-item ${activeTab === 'profile' ? 'active' : ''}`}
            style={{ width: 'auto', borderRadius: '0', borderBottom: activeTab === 'profile' ? '2px solid var(--primary)' : 'none' }}
            onClick={() => setActiveTab('profile')}
          >
            <User size={15} />
            <span>User & Brand</span>
          </button>
          <button
            type="button"
            className={`nav-item ${activeTab === 'ai' ? 'active' : ''}`}
            style={{ width: 'auto', borderRadius: '0', borderBottom: activeTab === 'ai' ? '2px solid var(--primary)' : 'none' }}
            onClick={() => setActiveTab('ai')}
          >
            <Cpu size={15} />
            <span>AI Model</span>
          </button>
          <button
            type="button"
            className={`nav-item ${activeTab === 'backend' ? 'active' : ''}`}
            style={{ width: 'auto', borderRadius: '0', borderBottom: activeTab === 'backend' ? '2px solid var(--primary)' : 'none' }}
            onClick={() => setActiveTab('backend')}
          >
            <Server size={15} />
            <span>Backend API</span>
          </button>
        </div>

        <form onSubmit={handleSave} className="modal-body">
          {/* Tab 1: Profile & Brand Configuration */}
          {activeTab === 'profile' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'flex', gap: '12px' }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>User Display Name</label>
                  <input
                    type="text"
                    className="search-input-wrapper"
                    style={{ width: '100%', marginTop: '4px', padding: '8px 12px' }}
                    value={formData.userProfile.name}
                    onChange={e => setFormData({ ...formData, userProfile: { ...formData.userProfile, name: e.target.value } })}
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>Email Address</label>
                  <input
                    type="email"
                    className="search-input-wrapper"
                    style={{ width: '100%', marginTop: '4px', padding: '8px 12px' }}
                    value={formData.userProfile.email}
                    onChange={e => setFormData({ ...formData, userProfile: { ...formData.userProfile, email: e.target.value } })}
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>Avatar Image URL</label>
                <input
                  type="url"
                  className="search-input-wrapper"
                  style={{ width: '100%', marginTop: '4px', padding: '8px 12px' }}
                  value={formData.userProfile.avatarUrl}
                  onChange={e => setFormData({ ...formData, userProfile: { ...formData.userProfile, avatarUrl: e.target.value } })}
                />
              </div>

              <div style={{ display: 'flex', gap: '12px' }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>App Branding Name</label>
                  <input
                    type="text"
                    className="search-input-wrapper"
                    style={{ width: '100%', marginTop: '4px', padding: '8px 12px' }}
                    value={formData.branding.appName}
                    onChange={e => setFormData({ ...formData, branding: { ...formData.branding, appName: e.target.value, logoText: e.target.value } })}
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>Tagline / Subtitle</label>
                  <input
                    type="text"
                    className="search-input-wrapper"
                    style={{ width: '100%', marginTop: '4px', padding: '8px 12px' }}
                    value={formData.branding.tagline}
                    onChange={e => setFormData({ ...formData, branding: { ...formData.branding, tagline: e.target.value } })}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Tab 2: AI Model Settings */}
          {activeTab === 'ai' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>Default AI Model</label>
                <select
                  style={{
                    width: '100%',
                    marginTop: '4px',
                    padding: '8px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-light)',
                    backgroundColor: 'var(--bg-input)',
                    color: 'var(--text-main)'
                  }}
                  value={formData.ai.defaultModel}
                  onChange={e => setFormData({ ...formData, ai: { ...formData.ai, defaultModel: e.target.value } })}
                >
                  <option value="gpt-4o">GPT-4o (Omni High Reasoning)</option>
                  <option value="gpt-4o-mini">GPT-4o-mini (Fast & Lightweight)</option>
                  <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
                  <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                  <option value="local-ollama">Local Ollama / Llama3</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>System Prompt</label>
                <textarea
                  rows={3}
                  className="search-input-wrapper prompt-textarea"
                  style={{ width: '100%', marginTop: '4px', padding: '8px 12px', fontSize: '13px' }}
                  value={formData.ai.systemPrompt}
                  onChange={e => setFormData({ ...formData, ai: { ...formData.ai, systemPrompt: e.target.value } })}
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>API Base URL</label>
                <input
                  type="text"
                  className="search-input-wrapper"
                  style={{ width: '100%', marginTop: '4px', padding: '8px 12px' }}
                  value={formData.ai.apiBaseUrl}
                  onChange={e => setFormData({ ...formData, ai: { ...formData.ai, apiBaseUrl: e.target.value } })}
                />
              </div>
            </div>
          )}

          {/* Tab 3: Backend Settings */}
          {activeTab === 'backend' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>Backend Execution Mode</label>
                <select
                  style={{
                    width: '100%',
                    marginTop: '4px',
                    padding: '8px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-light)',
                    backgroundColor: 'var(--bg-input)',
                    color: 'var(--text-main)'
                  }}
                  value={formData.backend.provider}
                  onChange={e => setFormData({ ...formData, backend: { ...formData.backend, provider: e.target.value as any } })}
                >
                  <option value="local-mock">Simulated In-Browser Multi-Tool Runner (Zero Setup)</option>
                  <option value="fastapi">Python FastAPI + LangChain Backend</option>
                  <option value="express">Node.js Express + Vercel AI SDK Backend</option>
                  <option value="openai-direct">Direct OpenAI API Integration</option>
                  <option value="custom-webhook">Custom Webhook REST Endpoint</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>Backend API Endpoint URL</label>
                <input
                  type="text"
                  className="search-input-wrapper"
                  style={{ width: '100%', marginTop: '4px', padding: '8px 12px' }}
                  value={formData.backend.endpointUrl}
                  onChange={e => setFormData({ ...formData, backend: { ...formData.backend, endpointUrl: e.target.value } })}
                />
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: '10px', marginTop: '12px' }}>
            <button
              type="button"
              className="upgrade-btn"
              style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
              onClick={handleReset}
            >
              <RotateCcw size={14} />
              <span>Reset Defaults</span>
            </button>

            <button
              type="submit"
              className="btn-new-chat"
              style={{ flex: 2, justifyContent: 'center' }}
            >
              <Save size={16} />
              <span>Save Configuration</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

import React, { useState } from 'react';
import { useChatContext } from '../context/ChatContext';
import { X, Code, Globe, Plus } from 'lucide-react';
import { CustomToolFormData } from '../types';

export const CustomToolModal: React.FC = () => {
  const { isCustomToolModalOpen, setIsCustomToolModalOpen, addCustomTool } = useChatContext();

  const [formData, setFormData] = useState<CustomToolFormData>({
    name: '',
    description: '',
    icon: '⚡',
    endpointUrl: '',
    method: 'GET',
    params: ''
  });

  if (!isCustomToolModalOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name || !formData.endpointUrl) return;
    addCustomTool(formData);
  };

  return (
    <div className="modal-overlay" onClick={() => setIsCustomToolModalOpen(false)}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Globe size={20} style={{ color: 'var(--primary)' }} />
            <h3 className="modal-title">Add Custom API Tool</h3>
          </div>
          <button className="btn-icon-subtle" onClick={() => setIsCustomToolModalOpen(false)}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body">
          <div style={{ display: 'flex', gap: '12px' }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Tool Name
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Weather Forecast API"
                className="search-input-wrapper"
                style={{ width: '100%', marginTop: '4px', padding: '8px 12px' }}
                value={formData.name}
                onChange={e => setFormData({ ...formData, name: e.target.value })}
              />
            </div>
            <div style={{ width: '80px' }}>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Icon Emoji
              </label>
              <input
                type="text"
                placeholder="🌤️"
                className="search-input-wrapper"
                style={{ width: '100%', marginTop: '4px', textAlign: 'center', padding: '8px' }}
                value={formData.icon}
                onChange={e => setFormData({ ...formData, icon: e.target.value })}
              />
            </div>
          </div>

          <div>
            <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Description
            </label>
            <input
              type="text"
              placeholder="Fetches live weather metrics by location query"
              className="search-input-wrapper"
              style={{ width: '100%', marginTop: '4px', padding: '8px 12px' }}
              value={formData.description}
              onChange={e => setFormData({ ...formData, description: e.target.value })}
            />
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <div style={{ width: '100px' }}>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                HTTP Method
              </label>
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
                value={formData.method}
                onChange={e => setFormData({ ...formData, method: e.target.value as 'GET' | 'POST' })}
              >
                <option value="GET">GET</option>
                <option value="POST">POST</option>
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Endpoint URL
              </label>
              <input
                type="url"
                required
                placeholder="https://api.example.com/v1/forecast"
                className="search-input-wrapper"
                style={{ width: '100%', marginTop: '4px', padding: '8px 12px' }}
                value={formData.endpointUrl}
                onChange={e => setFormData({ ...formData, endpointUrl: e.target.value })}
              />
            </div>
          </div>

          <div>
            <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Query Parameters / JSON Payload Schema (Optional)
            </label>
            <textarea
              rows={3}
              placeholder='{ "city": "{{location}}", "units": "metric" }'
              className="search-input-wrapper prompt-textarea"
              style={{ width: '100%', marginTop: '4px', padding: '8px 12px', fontFamily: 'monospace', fontSize: '13px' }}
              value={formData.params}
              onChange={e => setFormData({ ...formData, params: e.target.value })}
            />
          </div>

          <button
            type="submit"
            className="btn-new-chat"
            style={{ width: '100%', justifyContent: 'center', marginTop: '8px', padding: '10px' }}
          >
            <Plus size={16} />
            <span>Register & Enable Custom Plugin</span>
          </button>
        </form>
      </div>
    </div>
  );
};

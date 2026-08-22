import React from 'react';
import { useChatContext } from '../context/ChatContext';
import { X, Check, Sparkles, Zap, Shield, Infinity as UnlimitedIcon } from 'lucide-react';
import confetti from 'canvas-confetti';

export const UpgradeModal: React.FC = () => {
  const { isUpgradeModalOpen, setIsUpgradeModalOpen } = useChatContext();

  if (!isUpgradeModalOpen) return null;

  const handleUpgrade = () => {
    confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
    setIsUpgradeModalOpen(false);
  };

  return (
    <div className="modal-overlay" onClick={() => setIsUpgradeModalOpen(false)}>
      <div className="modal-content" style={{ maxWidth: '520px' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header" style={{ border: 'none', paddingBottom: '0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={20} style={{ color: 'var(--primary)' }} />
            <h3 className="modal-title">Upgrade to Clever Pro</h3>
          </div>
          <button className="btn-icon-subtle" onClick={() => setIsUpgradeModalOpen(false)}>
            <X size={18} />
          </button>
        </div>

        <div className="modal-body" style={{ textAlign: 'center', paddingTop: '10px' }}>
          <div style={{ margin: '16px 0' }}>
            <span style={{ fontSize: '40px', fontWeight: 800, color: 'var(--text-main)' }}>$20</span>
            <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}> / month</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', textAlign: 'left', margin: '12px 0' }}>
            {[
              'Unlimited Web Search & Live Code Interpreter access',
              'DALL-E 3 visual image generation in 4K resolution',
              'Custom API Webhook plugin builder & endpoint integration',
              'High priority GPT-4o & Claude 3.5 Sonnet processing',
              'Unlimited workspace team collaboration & prompt history'
            ].map((feature, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13.5px' }}>
                <div style={{ width: '20px', height: '20px', borderRadius: '50%', backgroundColor: 'var(--primary-light)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Check size={13} />
                </div>
                <span>{feature}</span>
              </div>
            ))}
          </div>

          <button
            className="btn-new-chat"
            style={{ width: '100%', justifyContent: 'center', padding: '12px', fontSize: '15px', marginTop: '12px' }}
            onClick={handleUpgrade}
          >
            <Zap size={18} fill="currentColor" />
            <span>Upgrade Account Now</span>
          </button>
        </div>
      </div>
    </div>
  );
};

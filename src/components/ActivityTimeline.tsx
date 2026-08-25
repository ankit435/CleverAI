import React, { useState } from 'react';
import { ActivityStep } from '../types';
import { ChevronDown, ChevronUp, Loader2, CheckCircle2, XCircle } from 'lucide-react';

interface ActivityTimelineProps {
  steps: ActivityStep[];
  /** True while the run is still in flight — keeps the timeline expanded and live. */
  isLive: boolean;
}

/**
 * Generic, tool-agnostic live activity timeline shown under an AI message while
 * (and after) an async agent run executes. Works the same way regardless of
 * which tool/agent produced each step (browser, sandbox/code execution, web
 * search, image generation, delegated sub-agents, etc.) — nothing here is
 * browser-specific.
 *
 * While the run is live, it stays expanded so the user can watch each real
 * step happen instead of staring at one frozen "Working on it…" line. Once the
 * run finishes, it collapses into a compact "View activity" toggle so the
 * chat stays clean, but the full step-by-step trace remains available.
 */
export const ActivityTimeline: React.FC<ActivityTimelineProps> = ({ steps, isLive }) => {
  const [expanded, setExpanded] = useState(isLive);

  if (!steps || steps.length === 0) return null;

  const showBody = isLive || expanded;

  return (
    <div
      className="activity-timeline"
      style={{
        marginTop: '8px',
        marginBottom: '4px',
        border: '1px solid var(--border-subtle)',
        borderRadius: '10px',
        overflow: 'hidden',
        background: 'var(--bg-surface)'
      }}
    >
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        disabled={isLive}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          width: '100%',
          padding: '8px 12px',
          background: 'transparent',
          border: 'none',
          cursor: isLive ? 'default' : 'pointer',
          fontSize: '12.5px',
          fontWeight: 600,
          color: 'var(--text-secondary)'
        }}
      >
        {isLive ? <Loader2 size={14} className="animate-spin" /> : (expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />)}
        <span>{isLive ? 'Working…' : 'View activity'}</span>
        <span style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--text-muted)', fontWeight: 400 }}>
          {steps.length} step{steps.length === 1 ? '' : 's'}
        </span>
      </button>

      {showBody && (
        <div style={{ padding: '0 12px 10px 12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {steps.map((step, idx) => (
            <div
              key={step.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '12.5px',
                color: step.status === 'error' ? 'var(--danger, #e5484d)' : 'var(--text-secondary)',
                opacity: isLive && idx === steps.length - 1 ? 1 : 0.85
              }}
            >
              {step.status === 'running' ? (
                <Loader2 size={13} className="animate-spin" style={{ flexShrink: 0 }} />
              ) : step.status === 'error' ? (
                <XCircle size={13} style={{ flexShrink: 0 }} />
              ) : (
                <CheckCircle2 size={13} style={{ flexShrink: 0, color: 'var(--primary)' }} />
              )}
              <span style={{ flex: 1 }}>{step.label}</span>
              {typeof step.durationMs === 'number' && (
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{step.durationMs}ms</span>
              )}
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{step.timestamp}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

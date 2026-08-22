import React from 'react';
import { ToolExecutionResult } from '../types';
import { Terminal, Globe, Image as ImageIcon, BarChart3, CheckCircle, ExternalLink } from 'lucide-react';

interface ToolWidgetProps {
  result: ToolExecutionResult;
}

export const ToolWidget: React.FC<ToolWidgetProps> = ({ result }) => {
  const { toolName, status, executionTimeMs, data } = result;

  const renderIcon = () => {
    switch (data?.type) {
      case 'image':
        return <ImageIcon size={15} />;
      case 'code':
        return <Terminal size={15} />;
      case 'search':
        return <Globe size={15} />;
      case 'chart':
        return <BarChart3 size={15} />;
      default:
        return <CheckCircle size={15} />;
    }
  };

  return (
    <div className="tool-execution-card">
      <div className="tool-card-header">
        {renderIcon()}
        <span>{toolName}</span>
        <span style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--text-muted)' }}>
          {executionTimeMs}ms
        </span>
      </div>

      {/* Render Image Output */}
      {data?.type === 'image' && data.imageUrl && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <img
            src={data.imageUrl}
            alt="AI Rendered Result"
            style={{
              width: '100%',
              maxHeight: '320px',
              objectFit: 'cover',
              borderRadius: '12px',
              border: '1px solid var(--border-light)'
            }}
          />
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
            Prompt: "{data.imagePrompt}"
          </div>
        </div>
      )}

      {/* Render Code Execution Output */}
      {data?.type === 'code' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {data.codeSnippet && (
            <div className="tool-output-box" style={{ backgroundColor: 'var(--bg-input)' }}>
              <code>{data.codeSnippet}</code>
            </div>
          )}
          {data.codeOutput && (
            <div className="tool-output-box" style={{ borderLeft: '3px solid var(--primary)', color: 'var(--badge-free-text)' }}>
              <strong>stdout &gt;</strong>
              <pre style={{ marginTop: '4px', whiteSpace: 'pre-wrap' }}>{data.codeOutput}</pre>
            </div>
          )}
        </div>
      )}

      {/* Render Web Search Results */}
      {data?.type === 'search' && data.searchResults && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {data.searchResults.map((item, idx) => (
            <a
              key={idx}
              href={item.url}
              target="_blank"
              rel="noreferrer"
              style={{
                textDecoration: 'none',
                display: 'block',
                padding: '10px 12px',
                backgroundColor: 'var(--bg-surface)',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle)',
                transition: 'border-color 0.2s'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '13.5px', fontWeight: 600, color: 'var(--primary)' }}>
                  {item.title}
                </span>
                <ExternalLink size={13} style={{ color: 'var(--text-muted)' }} />
              </div>
              <p style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                {item.snippet}
              </p>
            </a>
          ))}
        </div>
      )}

      {/* Render Chart Visualization */}
      {data?.type === 'chart' && data.chartData && (
        <div style={{ padding: '12px', backgroundColor: 'var(--bg-surface)', borderRadius: '10px' }}>
          <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '12px' }}>
            Interactive Quarterly Metric Chart
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: '16px', height: '140px', paddingTop: '10px' }}>
            {data.chartData.map((item, i) => (
              <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
                <div
                  style={{
                    width: '100%',
                    height: `${(item.value / 180) * 100}%`,
                    background: 'var(--primary-gradient)',
                    borderRadius: '6px 6px 0 0',
                    transition: 'height 0.5s ease-out'
                  }}
                />
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{item.label}</span>
                <span style={{ fontSize: '11px', fontWeight: 700 }}>{item.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

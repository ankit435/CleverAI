import React from 'react';
import { ToolExecutionResult } from '../types';
import { Terminal, Globe, Image as ImageIcon, BarChart3, CheckCircle, ExternalLink, Calculator, Cpu, Sparkles, Compass } from 'lucide-react';

interface ToolWidgetProps {
  result: ToolExecutionResult;
}

export const ToolWidget: React.FC<ToolWidgetProps> = ({ result }) => {
  const { toolName, status, executionTimeMs, data } = result;
  const [showLiveViewer, setShowLiveViewer] = React.useState(false);

  const renderIcon = () => {
    switch (data?.type) {
      case 'browser_page':
        return <Compass size={15} style={{ color: '#06b6d4' }} />;
      case 'image':
        return <ImageIcon size={15} />;
      case 'code':
        return <Terminal size={15} />;
      case 'custom_tool':
        return <Cpu size={15} style={{ color: 'var(--primary)' }} />;
      case 'calculation':
        return <Calculator size={15} />;
      case 'search':
        return <Globe size={15} />;
      case 'chart':
        return <BarChart3 size={15} />;
      default:
        return <Sparkles size={15} />;
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

      {/* Render Browser Web Page Navigation Output */}
      {data?.type === 'browser_page' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', backgroundColor: 'var(--bg-surface)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
            <div style={{ flex: 1, minWidth: 0, marginRight: '8px' }}>
              <div style={{ fontSize: '13.5px', fontWeight: 600, color: 'var(--text-main)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {data.title || 'Visited Webpage'}
              </div>
              {data.url && (
                <div style={{ fontSize: '11.5px', color: 'var(--primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {data.url}
                </div>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              {data.url && (
                <button
                  type="button"
                  onClick={() => setShowLiveViewer(!showLiveViewer)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '11.5px',
                    padding: '4px 8px',
                    borderRadius: '6px',
                    background: showLiveViewer ? 'var(--primary)' : 'var(--bg-input)',
                    color: showLiveViewer ? '#ffffff' : 'var(--text-main)',
                    border: '1px solid var(--border-subtle)',
                    cursor: 'pointer'
                  }}
                  title="Toggle In-App Live Browser View"
                >
                  <Compass size={12} />
                  <span>{showLiveViewer ? 'Hide View' : 'Live View'}</span>
                </button>
              )}
              {data.url && (
                <a
                  href={data.url}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '11.5px',
                    padding: '4px 8px',
                    borderRadius: '6px',
                    background: 'var(--bg-input)',
                    color: 'var(--text-main)',
                    textDecoration: 'none',
                    border: '1px solid var(--border-subtle)'
                  }}
                  title="Open live webpage in new browser tab"
                >
                  <ExternalLink size={12} />
                  <span>Open ↗</span>
                </a>
              )}
            </div>
          </div>

          {/* Action Log Badge */}
          {data.action && (
            <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: '#10b981' }} />
              <strong>Bot Action:</strong> {data.action}
            </div>
          )}

          {/* Interactive Live Browser Frame */}
          {showLiveViewer && data.url && (
            <div style={{ borderRadius: '10px', overflow: 'hidden', border: '1px solid var(--border-light)', backgroundColor: '#ffffff' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 12px', background: 'var(--bg-input)', borderBottom: '1px solid var(--border-subtle)', fontSize: '11px', color: 'var(--text-muted)' }}>
                <span style={{ fontFamily: 'monospace' }}>🌐 {data.url}</span>
                <span style={{ color: '#10b981', fontWeight: 600 }}>● Connected</span>
              </div>
              <iframe
                src={data.url}
                title="Interactive Web Preview"
                style={{ width: '100%', height: '340px', border: 'none' }}
                sandbox="allow-scripts allow-same-origin allow-popups"
              />
            </div>
          )}

          {/* Extracted Interactive Links Chips */}
          {data.links && data.links.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Interactive Links Found on Page ({data.links.length}):
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {data.links.map((link, lIdx) => (
                  <a
                    key={lIdx}
                    href={link.url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      fontSize: '11.5px',
                      padding: '3px 8px',
                      borderRadius: '12px',
                      background: 'var(--bg-surface)',
                      border: '1px solid var(--border-subtle)',
                      color: 'var(--primary)',
                      textDecoration: 'none',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    <span>{link.text}</span>
                    <ExternalLink size={10} style={{ opacity: 0.7 }} />
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Extracted Text Content Preview */}
          {data.content && (
            <div className="tool-output-box" style={{ fontSize: '12px', maxHeight: '160px', overflowY: 'auto' }}>
              <div style={{ fontSize: '10.5px', color: 'var(--text-muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>// Page Content Extracted</div>
              <div style={{ whiteSpace: 'pre-wrap', color: 'var(--text-secondary)' }}>{data.content}</div>
            </div>
          )}
        </div>
      )}

      {/* Render Custom Auto-Created Tool Output */}
      {data?.type === 'custom_tool' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {data.description && (
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              <strong>Purpose:</strong> {data.description}
            </div>
          )}
          {data.codeSnippet && (
            <div className="tool-output-box" style={{ backgroundColor: 'var(--bg-input)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>// Auto-Generated Python Code</div>
              <code>{data.codeSnippet}</code>
            </div>
          )}
          {data.codeOutput && (
            <div className="tool-output-box" style={{ borderLeft: '3px solid #10b981', color: 'var(--text-main)' }}>
              <strong style={{ color: '#10b981' }}>stdout &gt;</strong>
              <pre style={{ marginTop: '4px', whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{data.codeOutput}</pre>
            </div>
          )}
        </div>
      )}

      {/* Render Calculation Output */}
      {data?.type === 'calculation' && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', backgroundColor: 'var(--bg-surface)', borderRadius: '8px' }}>
          <div>
            <div style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>Expression:</div>
            <code style={{ fontSize: '13px', fontWeight: 600 }}>{data.expression}</code>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>Result:</div>
            <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--primary)' }}>{data.result}</span>
          </div>
        </div>
      )}

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

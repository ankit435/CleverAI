import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Copy, Check, Download, Eye, EyeOff } from 'lucide-react';

interface MarkdownRendererProps {
  content: string;
  isStreaming?: boolean;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, isStreaming }) => {
  return (
    <div className="rich-markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '');
            const language = match ? match[1] : '';
            const codeString = String(children).replace(/\n$/, '');

            if (!inline && (match || codeString.includes('\n'))) {
              return (
                <CodeBlock language={language || 'text'} code={codeString} />
              );
            }

            return (
              <code className="inline-code-badge" {...props}>
                {children}
              </code>
            );
          },
          table({ children }) {
            return (
              <div className="markdown-table-wrapper">
                <table className="markdown-table">{children}</table>
              </div>
            );
          },
          a({ href, children }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="markdown-link"
              >
                {children}
              </a>
            );
          },
          blockquote({ children }) {
            return <blockquote className="markdown-blockquote">{children}</blockquote>;
          },
          ul({ children }) {
            return <ul className="markdown-ul">{children}</ul>;
          },
          ol({ children }) {
            return <ol className="markdown-ol">{children}</ol>;
          },
          li({ children }) {
            return <li className="markdown-li">{children}</li>;
          },
          h1({ children }) {
            return <h1 className="markdown-h1">{children}</h1>;
          },
          h2({ children }) {
            return <h2 className="markdown-h2">{children}</h2>;
          },
          h3({ children }) {
            return <h3 className="markdown-h3">{children}</h3>;
          },
          p({ children }) {
            return <p className="markdown-p">{children}</p>;
          },
          hr() {
            return <hr className="markdown-hr" />;
          }
        }}
      >
        {content}
      </ReactMarkdown>
      {isStreaming && <span className="typing-cursor">▌</span>}
    </div>
  );
};

interface CodeBlockProps {
  language: string;
  code: string;
}

const EXTENSION_MAP: Record<string, string> = {
  javascript: 'js',
  js: 'js',
  typescript: 'ts',
  ts: 'ts',
  jsx: 'jsx',
  tsx: 'tsx',
  python: 'py',
  py: 'py',
  html: 'html',
  css: 'css',
  json: 'json',
  sql: 'sql',
  bash: 'sh',
  sh: 'sh',
  shell: 'sh',
  markdown: 'md',
  md: 'md',
  yaml: 'yml',
  yml: 'yml',
  svg: 'svg',
  text: 'txt'
};

const CodeBlock: React.FC<CodeBlockProps> = ({ language, code }) => {
  const [copied, setCopied] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  const langKey = language.toLowerCase().trim();
  const isPreviewable = ['html', 'svg', 'xml'].includes(langKey);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.warn('Copy to clipboard failed:', err);
    }
  };

  const handleDownload = () => {
    try {
      const ext = EXTENSION_MAP[langKey] || 'txt';
      const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `snippet_${Date.now()}.${ext}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.warn('Download snippet failed:', err);
    }
  };

  return (
    <div className="code-block-container">
      <div className="code-block-header">
        <span className="code-language-tag">{language}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {isPreviewable && (
            <button
              type="button"
              className="code-copy-btn"
              onClick={() => setShowPreview(!showPreview)}
              title={showPreview ? 'Show Code' : 'Preview HTML/SVG'}
            >
              {showPreview ? <EyeOff size={13} /> : <Eye size={13} />}
              <span>{showPreview ? 'Code' : 'Preview'}</span>
            </button>
          )}

          <button
            type="button"
            className="code-copy-btn"
            onClick={handleDownload}
            title="Download Code File"
          >
            <Download size={13} />
            <span>Download</span>
          </button>

          <button
            type="button"
            className="code-copy-btn"
            onClick={handleCopy}
            title="Copy code to clipboard"
          >
            {copied ? (
              <>
                <Check size={13} style={{ color: '#10b981' }} />
                <span style={{ color: '#10b981' }}>Copied!</span>
              </>
            ) : (
              <>
                <Copy size={13} />
                <span>Copy code</span>
              </>
            )}
          </button>
        </div>
      </div>

      {showPreview ? (
        <div style={{ padding: '16px', backgroundColor: '#ffffff', color: '#000000', overflow: 'auto' }}>
          <div dangerouslySetInnerHTML={{ __html: code }} />
        </div>
      ) : (
        <pre className="code-block-pre">
          <code>{code}</code>
        </pre>
      )}
    </div>
  );
};

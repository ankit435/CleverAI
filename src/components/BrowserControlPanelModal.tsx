import React, { useState, useEffect } from 'react';
import { 
  Globe, Compass, Terminal, Shield, RefreshCw, Power, CheckCircle, 
  AlertTriangle, ExternalLink, Plus, Trash2, Eye, Play, MousePointer, 
  ArrowLeft, ArrowRight, CornerDownLeft, X, Layers, Copy, Check
} from 'lucide-react';
import { apiClient } from '../config/apiClient';
import { BrowserSessionStatus, BrowserTabItem, BrowserSnapshotView, BrowserModeType } from '../types';

interface BrowserControlPanelModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const BrowserControlPanelModal: React.FC<BrowserControlPanelModalProps> = ({ isOpen, onClose }) => {
  const [status, setStatus] = useState<BrowserSessionStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [mode, setMode] = useState<BrowserModeType>('existing_cdp');
  const [cdpUrl, setCdpUrl] = useState('http://127.0.0.1:9222');
  const [newTabUrl, setNewTabUrl] = useState('');
  const [snapshot, setSnapshot] = useState<BrowserSnapshotView | null>(null);
  const [navUrl, setNavUrl] = useState('');
  const [clickTarget, setClickTarget] = useState('');
  const [typeText, setTypeText] = useState('');
  const [copiedCmd, setCopiedCmd] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);

  const chromeLaunchCommand = `google-chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome_dev_agent"`;

  const fetchStatus = async () => {
    try {
      setLoading(true);
      const data = await apiClient.browser.getStatus();
      setStatus(data);
      if (data.mode) setMode(data.mode);
      if (data.endpoint) setCdpUrl(data.endpoint);
    } catch (err: any) {
      console.warn('Failed to fetch browser status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchStatus();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleConnect = async () => {
    setActionLoading(true);
    setMessage({ text: 'Connecting to existing browser...', type: 'info' });
    try {
      const res = await apiClient.browser.connect({ mode, cdpUrl });
      if (res.success) {
        setMessage({ text: res.message || 'Connected to browser successfully!', type: 'success' });
        await fetchStatus();
      } else {
        setMessage({ text: res.message || 'Failed to connect.', type: 'error' });
      }
    } catch (err: any) {
      setMessage({ text: err.message || 'Connection error. Ensure Chrome is running with --remote-debugging-port=9222.', type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleDisconnect = async () => {
    setActionLoading(true);
    try {
      await apiClient.browser.disconnect();
      setMessage({ text: 'Disconnected from browser session.', type: 'info' });
      setSnapshot(null);
      await fetchStatus();
    } catch (err: any) {
      setMessage({ text: err.message || 'Disconnect error', type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleSelectTab = async (tabId: string) => {
    setActionLoading(true);
    try {
      const res = await apiClient.browser.selectTab(tabId);
      if (res.success) {
        setMessage({ text: `Focused tab ${tabId}`, type: 'success' });
        await fetchStatus();
      }
    } catch (err: any) {
      setMessage({ text: err.message, type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleOpenTab = async () => {
    let raw = newTabUrl.trim();
    if (!raw) return;
    if (!raw.startsWith('http://') && !raw.startsWith('https://') && !raw.startsWith('about:')) {
      if (raw.includes('.') && !raw.includes(' ')) {
        raw = `https://${raw}`;
      } else if (raw.toLowerCase() === 'youtube') {
        raw = 'https://www.youtube.com';
      } else if (raw.toLowerCase() === 'google') {
        raw = 'https://www.google.com';
      } else if (raw.toLowerCase() === 'github') {
        raw = 'https://github.com';
      } else if (raw.includes(' ')) {
        raw = `https://www.google.com/search?q=${encodeURIComponent(raw)}`;
      } else {
        raw = `https://www.${raw}.com`;
      }
    }
    setActionLoading(true);
    try {
      await apiClient.browser.openTab(raw);
      setNewTabUrl('');
      setMessage({ text: `Opened new tab (${raw})`, type: 'success' });
      await fetchStatus();
    } catch (err: any) {
      setMessage({ text: err.message, type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleCloseTab = async (tabId: string) => {
    setActionLoading(true);
    try {
      await apiClient.browser.closeTab(tabId);
      setMessage({ text: `Closed tab ${tabId}`, type: 'info' });
      await fetchStatus();
    } catch (err: any) {
      setMessage({ text: err.message, type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleTakeSnapshot = async () => {
    setActionLoading(true);
    try {
      const res = await apiClient.browser.snapshot();
      if (res.status === 'success' && res.snapshot) {
        setSnapshot(res.snapshot);
        setMessage({ text: `Captured DOM snapshot: ${res.snapshot.title}`, type: 'success' });
      } else {
        setMessage({ text: res.message || 'Failed to capture snapshot', type: 'error' });
      }
    } catch (err: any) {
      setMessage({ text: err.message, type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const handleExecuteAction = async (actionName: string, extra: any = {}) => {
    setActionLoading(true);
    try {
      const res = await apiClient.browser.executeAction({ action: actionName, ...extra });
      if (res.status === 'confirmation_required') {
        setMessage({ text: `⚠️ ${res.message}`, type: 'error' });
      } else if (res.status === 'success') {
        setMessage({ text: `⚡ ${res.message}`, type: 'success' });
        await fetchStatus();
      } else {
        setMessage({ text: res.message || 'Action failed', type: 'error' });
      }
    } catch (err: any) {
      setMessage({ text: err.message, type: 'error' });
    } finally {
      setActionLoading(false);
    }
  };

  const copyCommand = () => {
    navigator.clipboard.writeText(chromeLaunchCommand);
    setCopiedCmd(true);
    setTimeout(() => setCopiedCmd(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-4xl max-h-[90vh] shadow-2xl flex flex-col overflow-hidden text-slate-100">
        
        {/* Header */}
        <div className="p-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
              <Compass size={22} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white">Existing Browser AI Controller</h2>
                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold flex items-center gap-1 ${
                  status?.connected ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${status?.connected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`} />
                  {status?.connected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Connect and interact directly with your existing Chrome or Edge session without losing logins or cookies.
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Message Banner */}
        {message && (
          <div className={`px-4 py-2.5 text-xs font-medium border-b flex items-center justify-between ${
            message.type === 'success' ? 'bg-emerald-950/40 text-emerald-300 border-emerald-800/40' :
            message.type === 'error' ? 'bg-rose-950/40 text-rose-300 border-rose-800/40' :
            'bg-cyan-950/40 text-cyan-300 border-cyan-800/40'
          }`}>
            <span>{message.text}</span>
            <button onClick={() => setMessage(null)} className="opacity-70 hover:opacity-100">✕</button>
          </div>
        )}

        {/* Main Content Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">

          {/* Connection Controls Card */}
          <div className="p-4 rounded-xl bg-slate-950/40 border border-slate-800">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
              <Power size={14} className="text-cyan-400" />
              Connection Settings
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Connection Mode</label>
                <select 
                  value={mode}
                  onChange={(e) => setMode(e.target.value as BrowserModeType)}
                  className="w-full px-3 py-2 text-xs bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                >
                  <option value="existing_cdp">Existing Browser (CDP Port 9222)</option>
                  <option value="managed_browser">Managed Persistent Profile</option>
                  <option value="remote_browser">Remote Playwright Server</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-slate-400 mb-1 block">CDP Debugging URL</label>
                <input 
                  type="text"
                  value={cdpUrl}
                  onChange={(e) => setCdpUrl(e.target.value)}
                  placeholder="http://127.0.0.1:9222"
                  className="w-full px-3 py-2 text-xs bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="flex gap-2">
                <button
                  onClick={handleConnect}
                  disabled={actionLoading}
                  className="flex-1 px-4 py-2 text-xs font-medium rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white flex items-center justify-center gap-1.5 transition-all shadow-lg shadow-cyan-600/20 disabled:opacity-50"
                >
                  <RefreshCw size={13} className={actionLoading ? 'animate-spin' : ''} />
                  Connect
                </button>

                {status?.connected && (
                  <button
                    onClick={handleDisconnect}
                    disabled={actionLoading}
                    className="px-4 py-2 text-xs font-medium rounded-lg bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 flex items-center justify-center gap-1.5 transition-all"
                  >
                    <Power size={13} />
                    Disconnect
                  </button>
                )}
              </div>
            </div>

            {/* Launch Instructions Helper */}
            {!status?.connected && (
              <div className="mt-4 p-3 rounded-lg bg-slate-900/80 border border-slate-800 text-xs space-y-2">
                <div className="flex items-center justify-between text-slate-300 font-medium">
                  <span className="flex items-center gap-1.5">
                    <Terminal size={13} className="text-amber-400" />
                    How to start Chrome/Edge with Remote Debugging:
                  </span>
                  <button 
                    onClick={copyCommand}
                    className="flex items-center gap-1 text-[11px] text-cyan-400 hover:text-cyan-300 bg-slate-800 px-2 py-0.5 rounded border border-slate-700"
                  >
                    {copiedCmd ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                    {copiedCmd ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <pre className="p-2 rounded bg-black/40 text-amber-200/90 font-mono text-[11px] overflow-x-auto select-all">
                  {chromeLaunchCommand}
                </pre>
              </div>
            )}
          </div>

          {/* Open Tabs Manager */}
          {status?.connected && (
            <div className="p-4 rounded-xl bg-slate-950/40 border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                  <Layers size={14} className="text-cyan-400" />
                  Live Browser Tabs ({status.tabsCount})
                </h3>
                <button
                  onClick={fetchStatus}
                  disabled={loading}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 text-xs flex items-center gap-1"
                >
                  <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
                  Refresh
                </button>
              </div>

              {/* Tab List */}
              <div className="grid grid-cols-1 gap-2 max-h-48 overflow-y-auto">
                {status.tabs.map((tab) => (
                  <div 
                    key={tab.id}
                    className={`p-3 rounded-lg border flex items-center justify-between transition-all ${
                      tab.active 
                        ? 'bg-cyan-950/30 border-cyan-500/40 shadow-sm' 
                        : 'bg-slate-900/50 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0 pr-3">
                      <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                        {tab.id}
                      </span>
                      <div className="truncate">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-white truncate">{tab.title || 'Untitled'}</span>
                          {tab.active && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/30">
                              ACTIVE
                            </span>
                          )}
                        </div>
                        <a 
                          href={tab.url} 
                          target="_blank" 
                          rel="noreferrer" 
                          className="text-[11px] text-slate-400 hover:text-cyan-400 flex items-center gap-1 truncate mt-0.5"
                        >
                          {tab.url}
                          <ExternalLink size={10} />
                        </a>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      {!tab.active && (
                        <button
                          onClick={() => handleSelectTab(tab.id)}
                          className="px-2.5 py-1 text-xs rounded bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 transition-colors"
                        >
                          Focus
                        </button>
                      )}
                      <button
                        onClick={() => handleCloseTab(tab.id)}
                        className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-slate-800 transition-colors"
                        title="Close Tab"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Open New Tab Input */}
              <div className="flex gap-2 pt-2 border-t border-slate-800/80">
                <input
                  type="text"
                  value={newTabUrl}
                  onChange={(e) => setNewTabUrl(e.target.value)}
                  placeholder="Enter URL to open (e.g. https://github.com)"
                  className="flex-1 px-3 py-1.5 text-xs bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-cyan-500"
                />
                <button
                  onClick={handleOpenTab}
                  disabled={actionLoading || !newTabUrl.trim()}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 flex items-center gap-1.5 disabled:opacity-50"
                >
                  <Plus size={13} />
                  Open Tab
                </button>
              </div>
            </div>
          )}

          {/* Action Sandbox & DOM Snapshot */}
          {status?.connected && (
            <div className="p-4 rounded-xl bg-slate-950/40 border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
                  <Play size={14} className="text-cyan-400" />
                  Semantic Actions & DOM Inspector
                </h3>
                <button
                  onClick={handleTakeSnapshot}
                  disabled={actionLoading}
                  className="px-3 py-1.5 text-xs rounded-lg bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/30 flex items-center gap-1.5"
                >
                  <Eye size={13} />
                  Capture Snapshot
                </button>
              </div>

              {/* Quick Actions Row */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                <button
                  onClick={() => handleExecuteAction('go_back')}
                  className="p-2 text-xs rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 flex items-center justify-center gap-1.5 text-slate-300"
                >
                  <ArrowLeft size={13} /> Back
                </button>
                <button
                  onClick={() => handleExecuteAction('go_forward')}
                  className="p-2 text-xs rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 flex items-center justify-center gap-1.5 text-slate-300"
                >
                  <ArrowRight size={13} /> Forward
                </button>
                <button
                  onClick={() => handleExecuteAction('scroll', { direction: 'down', pixels: 500 })}
                  className="p-2 text-xs rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 flex items-center justify-center gap-1.5 text-slate-300"
                >
                  Scroll Down
                </button>
                <button
                  onClick={() => handleExecuteAction('screenshot')}
                  className="p-2 text-xs rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 flex items-center justify-center gap-1.5 text-slate-300"
                >
                  Screenshot
                </button>
              </div>

              {/* Snapshot Viewer */}
              {snapshot && (
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span className="font-semibold text-white truncate">{snapshot.title}</span>
                    <span>{snapshot.elements?.length || 0} interactive elements</span>
                  </div>

                  <div className="p-2 rounded bg-slate-950 font-mono text-[11px] text-slate-300 max-h-40 overflow-y-auto whitespace-pre-wrap">
                    {snapshot.formattedSnapshot}
                  </div>
                </div>
              )}
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between">
          <span className="text-[11px] text-slate-500 flex items-center gap-1">
            <Shield size={12} className="text-emerald-400" />
            Human-in-the-loop security enabled for dangerous transactions
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-white transition-colors"
          >
            Close Panel
          </button>
        </div>

      </div>
    </div>
  );
};

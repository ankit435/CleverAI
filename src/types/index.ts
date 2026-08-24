export type Theme = 'light' | 'dark';

export type ChatCategory = 'favorites' | 'code' | 'marketing' | 'archived' | 'deleted';

export interface CategoryInfo {
  id: ChatCategory;
  label: string;
  color: string;
}

export interface PluginCategoryInfo {
  id: string;
  label: string;
  color: string;
}

export interface Plugin {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  enabled: boolean;
  isAvailable?: boolean;
  statusMessage?: string;
  isCustom?: boolean;
  author?: string;
  version?: string;
  endpointUrl?: string;
  method?: 'GET' | 'POST';
  params?: any;
}

export interface ToolExecutionResult {
  toolId: string;
  toolName: string;
  status: 'running' | 'success' | 'error';
  executionTimeMs?: number;
  data?: {
    type?: 'image' | 'code' | 'search' | 'chart' | 'document' | 'raw' | 'browser_page' | 'custom_tool' | 'calculation';
    imageUrl?: string;
    imagePrompt?: string;
    codeSnippet?: string;
    codeOutput?: string;
    searchResults?: Array<{ title: string; snippet: string; url: string }>;
    chartType?: 'bar' | 'line' | 'donut';
    chartData?: Array<{ label: string; value: number }>;
    documentSummary?: string;
    documentFilename?: string;
    rawContent?: string;
    title?: string;
    url?: string;
    action?: string;
    links?: Array<{ text: string; url: string }>;
    content?: string;
    screenshotUrl?: string;
    toolName?: string;
    description?: string;
    expression?: string;
    result?: any;
  };
}

export interface Message {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  timestamp: string;
  toolResults?: ToolExecutionResult[];
  isStreaming?: boolean;
  /** Live progress label shown while an async SSE-tracked run is still in flight (e.g. "Executing browser_act"). */
  statusText?: string;
  /** Server-correlated agent run ID; present while a message is backed by an in-flight async run (used for cancel). */
  runId?: string;
}

export interface ChatThread {
  id: string;
  title: string;
  category: ChatCategory;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
  activePluginIds: string[];
}

export interface PromptTemplate {
  id: string;
  title: string;
  description: string;
  category: string;
  prompt: string;
  icon: string;
}

export interface CustomToolFormData {
  name: string;
  description: string;
  icon: string;
  endpointUrl: string;
  method: 'GET' | 'POST';
  params: string;
}

// Browser Agent Platform Types
export type BrowserModeType = 'existing_cdp' | 'existing_extension' | 'managed_browser' | 'remote_browser';

export interface BrowserTabItem {
  id: string;
  title: string;
  url: string;
  active: boolean;
  favicon?: string;
  windowId?: string;
}

export interface BrowserInteractiveElement {
  description: string;
  method: string;
}

export interface BrowserActionResult {
  action: string;
  status: 'success' | 'error' | 'confirmation_required';
  message: string;
  durationMs?: number;
  currentUrl?: string;
  currentTitle?: string;
  data?: Record<string, any> | null;
  error?: string | null;
}

export interface BrowserSessionStatus {
  connected: boolean;
  mode: BrowserModeType;
  endpoint?: string;
  browserType?: string;
  version?: string;
  tabsCount: number;
  activeTab?: BrowserTabItem | null;
  tabs: BrowserTabItem[];
  userId?: number;
  error?: string;
}

export interface BrowserConfirmationRequest {
  id: string;
  userId: number;
  sessionId: string;
  action: string;
  target: string;
  params: Record<string, any>;
  reason: string;
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  status: 'pending' | 'approved' | 'rejected' | 'expired';
  createdAt: string;
  expiresAt: string;
}

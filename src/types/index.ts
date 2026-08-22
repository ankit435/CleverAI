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
    type: 'image' | 'code' | 'search' | 'chart' | 'document' | 'raw';
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
  };
}

export interface Message {
  id: string;
  sender: 'user' | 'ai';
  text: string;
  timestamp: string;
  toolResults?: ToolExecutionResult[];
  isStreaming?: boolean;
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

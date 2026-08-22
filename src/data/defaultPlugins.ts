import { Plugin, CategoryInfo } from '../types';

export const CATEGORIES: CategoryInfo[] = [
  { id: 'favorites', label: 'Favorites', color: '#06b6d4' },
  { id: 'code', label: 'Code', color: '#f59e0b' },
  { id: 'marketing', label: 'Marketing', color: '#10b981' },
  { id: 'archived', label: 'Archived', color: '#ef4444' },
  { id: 'deleted', label: 'Deleted', color: '#f97316' }
];

export const INITIAL_PLUGINS: Plugin[] = [
  {
    id: 'browser-agent',
    name: 'Browser AI Agent',
    description: 'Connects to your existing browser session to navigate, inspect DOM, click, and manage tabs.',
    icon: '🧭',
    category: 'search',
    enabled: true,
    author: 'Clever AI',
    version: '2.0.0'
  },
  {
    id: 'web-search',
    name: 'Web Search Engine',
    description: 'Searches real-time internet information with live source citations.',
    icon: '🌐',
    category: 'search',
    enabled: true,
    author: 'Clever AI',
    version: '2.4.0'
  },
  {
    id: 'code-interpreter',
    name: 'Code Sandbox Interpreter',
    description: 'Executes JS/Python code snippets in a safe isolated runtime environment.',
    icon: '💻',
    category: 'code',
    enabled: true,
    author: 'Clever AI',
    version: '3.1.0'
  },
  {
    id: 'dalle3-image',
    name: 'DALL-E 3 Visual Studio',
    description: 'Generates ultra high-definition artwork, mockups, and UI assets.',
    icon: '🎨',
    category: 'creative',
    enabled: true,
    author: 'OpenAI Studio',
    version: '1.8.2'
  },
  {
    id: 'data-viz',
    name: 'Chart & Graph Builder',
    description: 'Transforms tabular data and metrics into interactive visual charts.',
    icon: '📊',
    category: 'data',
    enabled: true,
    author: 'Clever AI',
    version: '1.2.0'
  },
  {
    id: 'doc-parser',
    name: 'PDF & Document Analyzer',
    description: 'Extracts key insights, summaries, and quotes from uploaded files.',
    icon: '📄',
    category: 'document',
    enabled: false,
    author: 'Clever AI',
    version: '1.0.5'
  }
];

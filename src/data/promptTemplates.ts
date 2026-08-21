import { PromptTemplate } from '../types';

export const PROMPT_TEMPLATES: PromptTemplate[] = [
  {
    id: '1',
    title: 'Generate UI Component',
    description: 'Create a responsive React + Tailwind or CSS component',
    category: 'Code',
    icon: '⚡',
    prompt: 'Design and build a responsive React navbar component with light/dark theme toggle, search bar, and smooth mobile menu drawer animation.'
  },
  {
    id: '2',
    title: 'Executive Summary',
    description: 'Summarize long documents into concise bullet points',
    category: 'Productivity',
    icon: '📝',
    prompt: 'Please provide a 3-bullet executive summary and key action items for the following project proposal.'
  },
  {
    id: '3',
    title: 'Marketing Campaign Plan',
    description: 'Outline a 4-week launch strategy for a SaaS product',
    category: 'Marketing',
    icon: '🚀',
    prompt: 'Create a 4-week multi-channel marketing campaign launch plan for a new AI productivity app, including target personas, channel strategy, and key metrics.'
  },
  {
    id: '4',
    title: 'Python Script Refactor',
    description: 'Optimize Python code for performance and readability',
    category: 'Code',
    icon: '💻',
    prompt: 'Refactor this Python script to use async execution, add type hints, and improve exception handling.'
  },
  {
    id: '5',
    title: 'Generate Creative Image',
    description: 'Detailed DALL-E prompt for futuristic UI mockup',
    category: 'Creative',
    icon: '🎨',
    prompt: 'Generate a futuristic 3D render of a futuristic dashboard interface floating in a dark sleek space station background with glowing purple and cyan holographic charts.'
  }
];

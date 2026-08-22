export interface AppConfig {
  branding: {
    appName: string;
    logoText: string;
    tagline: string;
  };
  userProfile: {
    name: string;
    email: string;
    avatarUrl: string;
    plan: string;
  };
  ai: {
    defaultModel: string;
    systemPrompt: string;
    temperature: number;
    apiBaseUrl: string;
    apiKey: string;
  };
  backend: {
    provider: 'local-mock' | 'fastapi' | 'express' | 'openai-direct' | 'custom-webhook';
    endpointUrl: string;
  };
}

export const DEFAULT_APP_CONFIG: AppConfig = {
  branding: {
    appName: 'Clever',
    logoText: 'Clever',
    tagline: 'Ask anything, explore possibilities, and get instant insights—all in one prompt.'
  },
  userProfile: {
    name: '',
    email: '',
    avatarUrl: '',
    plan: 'Free'
  },
  ai: {
    defaultModel: 'nvidia/nemotron-3.5-lightning-30b-a3b',
    systemPrompt: 'You are a helpful AI workspace assistant equipped with multi-tool capabilities.',
    temperature: 1.0,
    apiBaseUrl: 'https://api.openai.com/v1',
    apiKey: ''
  },
  backend: {
    provider: 'express',
    endpointUrl: '/api/v1/chat'
  }
};

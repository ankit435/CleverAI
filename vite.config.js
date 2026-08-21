import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: false,
    proxy: {
      // Reverse Proxy for Node.js Express Auth API (Port 8000)
      '/api/v1/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      },
      // Reverse Proxy for Python FastAPI LangChain AI Server (Port 8001)
      '/api/v1/pychat': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api\/v1\/pychat/, '/api/v1/chat')
      },
      // Reverse Proxy fallback to Express Backend (Port 8000)
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false
      }
    }
  }
})



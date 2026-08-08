import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite' 

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || process.env.API_PROXY_TARGET || 'http://127.0.0.1:5000'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(), 
  ],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setupTests.js',
    globals: true,
  },
  server: {
    host: true, 
    port: 3000,
    proxy: {
      '/api': apiProxyTarget
    }
  }
})
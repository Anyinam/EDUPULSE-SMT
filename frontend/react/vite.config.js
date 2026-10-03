import { defineConfig, loadEnv } from 'vite'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite' 

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, fileURLToPath(new URL('.', import.meta.url)), 'VITE_')
  const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || env.VITE_API_PROXY_TARGET || process.env.API_PROXY_TARGET || 'http://127.0.0.1:5000'
  const publicProxyTarget = process.env.VITE_PUBLIC_API_PROXY_TARGET || env.VITE_PUBLIC_API_PROXY_TARGET
  const publicProxy = publicProxyTarget ? {
    target: publicProxyTarget,
    changeOrigin: true,
    bypass(request) {
      if (!['GET', 'HEAD'].includes(request.method)) return false
    },
    configure(proxy) {
      proxy.on('proxyReq', (request) => {
        request.removeHeader('authorization')
        request.removeHeader('cookie')
      })
    },
  } : null
  return {
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
      ...(publicProxy ? {
        '^/api/subscription/plans(?:\\?|$)': publicProxy,
        '^/api/public/platform-content(?:\\?|$)': publicProxy,
      } : {}),
      '/api': apiProxyTarget
    }
  }
  }
})
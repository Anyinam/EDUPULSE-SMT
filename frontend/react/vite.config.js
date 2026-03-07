import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite' 

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(), 
  ],
  server: {
    host: true, 
    port: 3000,
    proxy: {
      '/api': 'http://backend:5000'
    }
  }
})
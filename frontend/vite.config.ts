import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { previewSecurityHeaders } from './securityHeaders'

export default defineConfig({
  plugins: [react()],
  preview: {
    headers: previewSecurityHeaders,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})

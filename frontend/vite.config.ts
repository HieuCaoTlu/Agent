import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    // Backend (FastAPI/uvicorn) chạy ở :8000 (Mục Q). WebSocket giọng nói
    // (K) đi qua cùng proxy này — `ws: true` bắt buộc để Vite không coi
    // `/api/v1/sessions/{id}/voice` là request HTTP thường.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})

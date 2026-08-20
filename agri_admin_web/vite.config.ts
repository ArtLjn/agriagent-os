import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api/agent': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/agent/, '/api/agri_backend_v2'),
      },
      '/api/admin/traces': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/admin/, '/api/agri_backend_v2'),
      },
      '/api': {
        target: 'http://localhost:9876',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/api/agri_backend_v2'),
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
  },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/app/',
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined

          if (id.includes('react-router')) return 'vendor-router'
          if (id.includes('@tanstack/react-query')) return 'vendor-query'
          if (id.includes('react-hook-form') || id.includes('zod')) return 'vendor-forms'
          if (id.includes('axios')) return 'vendor-http'
          if (id.includes('recharts')) return 'vendor-charts'
          if (id.includes('zustand')) return 'vendor-state'
          if (id.includes('react') || id.includes('scheduler')) return 'vendor-react'

          return 'vendor-misc'
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:5000',
      '/health': 'http://127.0.0.1:5000',
      '/manual_submit': 'http://127.0.0.1:5000',
      '/agent': 'http://127.0.0.1:5000',
      '/features': 'http://127.0.0.1:5000',
    },
  },
})

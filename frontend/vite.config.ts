import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:8007',
        changeOrigin: true
      }
    }
  },
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks: {
          // 将大型第三方库拆分为独立 chunk，避免全部打包进 index
          'vendor-ui': ['element-plus'],
          'vendor-chart': ['echarts'],
          'vendor-markdown': ['marked'],
          'vendor-http': ['axios'],
          'vendor-vue': ['vue', 'vue-router', 'pinia'],
        },
      },
    },
  },
})

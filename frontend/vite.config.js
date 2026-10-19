import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

export default defineConfig({
  plugins: [vue()],

  // —— 关键：@ 别名 → src 目录，所有 import '@/xxx' 都能解析 ——
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },

  server: {
    host: '0.0.0.0',
    port: 5173,
    // 内网穿透（cpolar / 花生壳 / frp 等）访问时 Host 是随机域名，
    // vite 5.4.12+ 默认会拦截未知 Host 并返回 403 "Blocked request"。
    // 开发/演示环境放开；正式部署建议改成具体域名数组，如 ['review.example.com']。
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },

  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})

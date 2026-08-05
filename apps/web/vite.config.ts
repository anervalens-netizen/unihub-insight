import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3100,
    strictPort: true,
  },
  preview: {
    port: 3100,
    strictPort: true,
  },
  build: {
    target: 'es2022',
    sourcemap: true,
    cssCodeSplit: true,
    reportCompressedSize: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalized = id.replaceAll('\\', '/');
          if (!normalized.includes('/node_modules/')) return undefined;
          if (
            normalized.includes('/react/') ||
            normalized.includes('/react-dom/') ||
            normalized.includes('/scheduler/')
          ) {
            return 'vendor-react';
          }
          if (normalized.includes('/@tanstack/')) return 'vendor-tanstack';
          if (normalized.includes('/gridstack/')) return 'vendor-grid';
          if (normalized.includes('/echarts/') || normalized.includes('/zrender/')) {
            return 'vendor-charts';
          }
          return 'vendor';
        },
      },
    },
  },
});

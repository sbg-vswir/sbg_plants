import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],

  // Local dev server options (you can keep them)
  server: {
    port: 3000,
    open: true,
  },
  
  preview: {
    port: 3000, 
  },

  // Production build options
  build: {
    outDir: 'dist', // folder to deploy
    emptyOutDir: true, // clear folder before build
  },

  // Important for routing and asset paths
  base: '/', // ensures assets reference root, works with CloudFront/S3
});

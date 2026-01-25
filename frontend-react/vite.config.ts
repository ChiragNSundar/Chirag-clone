/// <reference types="vitest/config" />
import { defineConfig, mergeConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// Base Vite config
const viteConfig = defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['vite.svg'],
      manifest: {
        name: 'Chirag Clone - Digital Twin',
        short_name: 'Chirag Clone',
        description: 'Personal AI Digital Twin with voice, vision, and memory.',
        theme_color: '#1e1e2e',
        background_color: '#1e1e2e',
        display: 'standalone',
        start_url: '/',
        icons: [
          {
            src: 'vite.svg',
            sizes: '192x192',
            type: 'image/svg+xml',
            purpose: 'any'
          },
          {
            src: 'vite.svg',
            sizes: '512x512',
            type: 'image/svg+xml',
            purpose: 'any maskable'
          }
        ]
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff,woff2}'],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365 // 1 year
              },
              cacheableResponse: {
                statuses: [0, 200]
              }
            }
          },
          {
            urlPattern: /\/api\/.*\/drafts/,
            method: 'POST',
            handler: 'NetworkOnly',
            options: {
              backgroundSync: {
                name: 'drafts-queue',
                options: {
                  maxRetentionTime: 24 * 60 // Retry for max of 24 Hours
                }
              }
            }
          },
          {
            urlPattern: /\/api\/training\/journal/,
            method: 'POST',
            handler: 'NetworkOnly',
            options: {
              backgroundSync: {
                name: 'journal-queue',
                options: {
                  maxRetentionTime: 24 * 60
                }
              }
            }
          }
        ]
      }
    })
  ]
})

// Vitest config merged in
export default mergeConfig(viteConfig, {
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
    include: ['**/*.{test,spec}.{ts,tsx}'],
    coverage: {
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', 'src/test/']
    },
    exclude: ['node_modules', 'e2e', 'dist']
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-ui': ['framer-motion', 'lucide-react', 'clsx', 'tailwind-merge'],
          'vendor-3d': ['three', '@react-three/fiber', '@react-three/drei'],
          'vendor-utils': ['date-fns', 'recharts']
        }
      }
    }
  }
})

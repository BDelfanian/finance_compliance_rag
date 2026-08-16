import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // src/config.py's api_cors_origins already allows this exact origin.
  server: { port: 5173 },
})

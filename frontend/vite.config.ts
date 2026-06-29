import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Em desenvolvimento, o frontend roda em http://localhost:5173 e o backend
// FastAPI em http://localhost:8000. O "proxy" abaixo faz o Vite encaminhar as
// chamadas de /analise e /health para o backend, então no código do app a
// gente chama só "/analise" (mesma origem) e não precisa lidar com CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/analise': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})

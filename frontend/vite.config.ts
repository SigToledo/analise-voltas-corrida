import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Em desenvolvimento, o frontend roda em http://localhost:5173 e o backend
// FastAPI em http://localhost:8000. O "proxy" abaixo faz o Vite encaminhar as
// chamadas de /analise e /health para o backend, então no código do app a
// gente chama só "/analise" (mesma origem) e não precisa lidar com CORS.
//
// BACKEND_PORT troca a porta do backend de desenvolvimento: com o app
// instalado aberto, o backend dele já ocupa a 8000 (ex.: BACKEND_PORT=8001).
const backend = `http://localhost:${process.env.BACKEND_PORT ?? '8000'}`

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/analise': backend,
      '/health': backend,
    },
  },
})

import type { AnaliseSessao } from './types'

// Base da API. Em desenvolvimento usamos caminho relativo ("/analise"), que o
// proxy do Vite encaminha para o backend. No app empacotado (Tauri) não há
// proxy, então falamos direto com o backend local na porta 8000.
// (Enquanto o backend não vira "sidecar", ele precisa estar rodando.)
const API_BASE = import.meta.env.PROD ? 'http://localhost:8000' : ''

/**
 * Envia o PDF para o backend e devolve a análise.
 *
 * Lança um Error com mensagem amigável se o backend recusar o arquivo (ex:
 * PDF inválido / não é Laptimes), para a tela de upload mostrar o erro sem
 * inventar nenhum dado.
 */
export async function analisarPdf(arquivo: File): Promise<AnaliseSessao> {
  const form = new FormData()
  form.append('arquivo', arquivo)

  let resposta: Response
  try {
    resposta = await fetch(`${API_BASE}/analise`, { method: 'POST', body: form })
  } catch {
    // Erro de rede: backend provavelmente não está rodando.
    throw new Error(
      'Não foi possível falar com o servidor de análise. Confira se o backend está rodando.',
    )
  }

  if (!resposta.ok) {
    // O backend manda { "detail": "..." } nos erros (400/422).
    let detalhe = `Erro ${resposta.status} ao analisar o PDF.`
    try {
      const corpo = await resposta.json()
      if (corpo?.detail) detalhe = corpo.detail
    } catch {
      // resposta sem JSON — mantém a mensagem padrão
    }
    throw new Error(detalhe)
  }

  return (await resposta.json()) as AnaliseSessao
}

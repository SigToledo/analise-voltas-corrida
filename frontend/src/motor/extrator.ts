/**
 * Motor de análise — Etapa 1: extração de texto com coordenadas via pdf.js.
 *
 * Substitui o papel do pdfplumber (backend Python) no aparelho: lê o PDF e
 * devolve as "palavras" com posição, que o parser usa para reconstruir a
 * tabela de voltas. As coordenadas não são idênticas às do pdfplumber (cada
 * biblioteca mede um pouco diferente); o que o porte exige é que a SAÍDA do
 * parser (voltas, tempos, flags) reproduza o gabarito gerado pelo Python.
 *
 * FALSO NEGRITO: o cronômetro imprime os valores em destaque 3-4 vezes quase
 * na mesma posição para simular negrito. No pdf.js cada impressão vira um
 * item separado — removemos as cópias que ficam a <1pt da primeira, senão
 * cada tempo em destaque apareceria repetido.
 */

import * as pdfjs from 'pdfjs-dist/legacy/build/pdf.mjs'

export interface Palavra {
  texto: string
  x0: number // borda esquerda, em pontos de PDF
  x1: number // borda direita
  top: number // distância do TOPO da página (mesma convenção do backend)
}

export interface PaginaExtraida {
  numero: number
  largura: number
  altura: number
  palavras: Palavra[]
}

/** Extrai todas as páginas do PDF (bytes) como listas de palavras posicionadas. */
export async function extrairPaginas(dados: Uint8Array): Promise<PaginaExtraida[]> {
  const tarefa = pdfjs.getDocument({ data: dados })
  const doc = await tarefa.promise
  const paginas: PaginaExtraida[] = []

  for (let n = 1; n <= doc.numPages; n++) {
    const pagina = await doc.getPage(n)
    const viewport = pagina.getViewport({ scale: 1 })
    const conteudo = await pagina.getTextContent()

    const brutas: Palavra[] = []
    for (const item of conteudo.items) {
      if (!('str' in item) || item.str.trim() === '') continue
      // transform = [a,b,c,d,e,f]: e = x, f = y (origem no RODAPÉ da página).
      const x = item.transform[4] as number
      const y = item.transform[5] as number
      const alturaItem = Math.hypot(item.transform[2] as number, item.transform[3] as number)
      const top = viewport.height - y - alturaItem

      // O pdf.js devolve "runs" que podem conter várias palavras (ex.:
      // "(171) L.JOSE" num item só). O parser trabalha por PALAVRA, então
      // quebramos o run nos espaços, estimando a posição de cada pedaço
      // proporcionalmente à largura do item. É aproximado (fonte não é
      // monoespaçada), mas os valores numéricos das colunas vêm em itens
      // próprios — a aproximação só afeta nomes, onde posição exata não
      // importa.
      const texto = item.str
      const larguraPorChar = item.width / Math.max(texto.length, 1)
      const re = /\S+/g
      let m: RegExpExecArray | null
      while ((m = re.exec(texto)) !== null) {
        brutas.push({
          texto: m[0],
          x0: x + m.index * larguraPorChar,
          x1: x + (m.index + m[0].length) * larguraPorChar,
          top,
        })
      }
    }

    paginas.push({
      numero: n,
      largura: viewport.width,
      altura: viewport.height,
      palavras: removerFalsoNegrito(brutas),
    })
  }

  await tarefa.destroy()
  return paginas
}

/**
 * Remove as cópias do "falso negrito": itens com o MESMO texto a menos de
 * 1pt de distância da primeira ocorrência são duplicatas de impressão.
 * (O mesmo tratamento que o backend faz por caractere, aqui por item.)
 */
export function removerFalsoNegrito(palavras: Palavra[]): Palavra[] {
  const mantidas: Palavra[] = []
  for (const p of palavras) {
    const duplicata = mantidas.some(
      (m) =>
        m.texto === p.texto && Math.abs(m.x0 - p.x0) < 1.0 && Math.abs(m.top - p.top) < 1.0,
    )
    if (!duplicata) mantidas.push(p)
  }
  return mantidas
}

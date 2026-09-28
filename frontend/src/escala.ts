// Escala do eixo Y do gráfico de tempo por volta. Funções puras, testadas
// em escala.test.ts.

/**
 * Uma volta só entra na JANELA do gráfico se estiver a até 7% da melhor
 * volta do próprio piloto (a regra dos 107%: acima disso não é volta de
 * ataque — é volta de desaquecimento, tráfego pesado ou problema). Ela
 * continua desenhada; só não estica a escala.
 */
export const LIMITE_JANELA = 1.07

/** Passos "redondos" para os rótulos do eixo, em segundos. */
const PASSOS = [0.2, 0.5, 1, 2, 5, 10, 15, 30, 60]

/**
 * Rótulos do eixo em valores redondos (ex.: 1:17, 1:18, 1:19…), com no
 * máximo ~6 marcas. Sem isso o eixo mostra 1:17.200, 1:25.200…
 */
export function marcasEixo(min: number, max: number, maxMarcas = 6): number[] {
  if (!(max > min)) return []
  const passo = PASSOS.find((p) => (max - min) / p <= maxMarcas) ?? 60
  const marcas: number[] = []
  // Arredonda para evitar 77.00000001 por erro de ponto flutuante.
  for (let t = Math.ceil(min / passo) * passo; t <= max + 1e-9; t += passo) {
    marcas.push(Math.round(t * 1000) / 1000)
  }
  return marcas
}

/**
 * Espaço de cada "linha" de marcadores (P, S, L, ×) no rodapé do gráfico,
 * em segundos do eixo: proporcional à altura da escala, para as letras
 * nunca se encostarem, seja a escala de 3 s ou de 30 s.
 */
export function passoMarcadores(min: number, max: number): number {
  return Math.max(0.35, (max - min) * 0.06)
}

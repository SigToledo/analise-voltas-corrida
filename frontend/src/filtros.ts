// Filtros dos pilotos na tela: por GRUPO (turma da sessão, ex.: G1/G2) e
// por CLASSE (ELITE, MASTER, SUPER — vem do resumo oficial). Funções puras,
// testadas em filtros.test.ts.

import type { MetricasPiloto } from './types'

export interface Filtros {
  grupo: string | null
  classe: string | null
}

export const SEM_FILTRO: Filtros = { grupo: null, classe: null }

/** Os pilotos que passam nos dois filtros (null = sem filtro). */
export function aplicarFiltros(pilotos: MetricasPiloto[], filtros: Filtros): MetricasPiloto[] {
  return pilotos.filter(
    (p) =>
      (filtros.grupo === null || p.grupo === filtros.grupo) &&
      (filtros.classe === null || p.classe === filtros.classe),
  )
}

/**
 * Classes presentes na sessão e quantos pilotos cada uma tem, em ordem
 * alfabética. Vazio quando nenhum piloto tem classe (resumo não enviado):
 * a classe nunca é deduzida.
 */
export function classesDaSessao(pilotos: MetricasPiloto[]): { classe: string; num_pilotos: number }[] {
  const contagem = new Map<string, number>()
  for (const p of pilotos) {
    if (p.classe) contagem.set(p.classe, (contagem.get(p.classe) ?? 0) + 1)
  }
  return [...contagem.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([classe, num_pilotos]) => ({ classe, num_pilotos }))
}

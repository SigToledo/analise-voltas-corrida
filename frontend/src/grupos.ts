// Grupos da sessão (ex.: MBR treina em Grupo 1 e Grupo 2). Funções puras,
// testadas em grupos.test.ts.

import type { GrupoSessao, MetricasPiloto } from './types'

/** "11/09/2026 08:45" -> "08h45" (null se não houver hora). */
export function horaDoGrupo(dataHora: string | null): string | null {
  const hora = dataHora?.split(' ')[1]
  if (!hora) return null
  const [h, m] = hora.split(':')
  return `${h.padStart(2, '0')}h${m}`
}

/**
 * Aviso quando a comparação mistura grupos: eles andam em horários
 * diferentes, e a pista muda entre um e outro (borracha, temperatura).
 * null se todos os selecionados são do mesmo grupo.
 */
export function avisoGruposMisturados(
  grupos: GrupoSessao[],
  pilotos: MetricasPiloto[],
  selecionados: string[],
): string | null {
  const usados = new Set(
    selecionados
      .map((c) => pilotos.find((p) => p.numero_carro === c)?.grupo)
      .filter((g): g is string => !!g),
  )
  if (usados.size < 2) return null
  const horarios = grupos
    .filter((g) => usados.has(g.sigla))
    .map((g) => {
      const hora = horaDoGrupo(g.data_hora)
      return hora ? `${g.sigla} às ${hora}` : g.sigla
    })
  return `Pilotos de grupos diferentes (${horarios.join(' · ')}): a pista pode ter mudado entre um grupo e outro.`
}

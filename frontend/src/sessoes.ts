// Sessões dos PDFs enviados (ex.: o documento oficial compilado traz o
// Classificatório e o Top Qualifying). Funções puras, testadas em
// sessoes.test.ts.

import type { SessaoDisponivel } from './types'

/** "10/10/2026 13:40" -> "10/10" (null se não houver data). */
function diaDaSessao(dataHora: string | null): string | null {
  const dia = dataHora?.split(' ')[0]
  return dia ? dia.split('/').slice(0, 2).join('/') : null
}

/** "11/09/2026 8:45" -> "08:45", como no cronômetro (null se não houver hora). */
function horaDaSessao(dataHora: string | null): string | null {
  const hora = dataHora?.split(' ')[1]
  return hora ? hora.padStart(5, '0') : null
}

/**
 * Texto do botão de cada sessão no seletor: o nome do PDF e a hora de início
 * ("CLASSIFICATORIO - FT · 13:40"). Se as sessões enviadas são de dias
 * diferentes, a data entra também ("11/09 13:40"), senão a hora sozinha
 * confunde.
 */
export function rotuloSessao(sessao: SessaoDisponivel, todas: SessaoDisponivel[]): string {
  const dias = new Set(todas.map((s) => diaDaSessao(s.data_hora)))
  const hora = horaDaSessao(sessao.data_hora)
  const dia = dias.size > 1 ? diaDaSessao(sessao.data_hora) : null
  const quando = [dia, hora].filter(Boolean).join(' ')
  const nome = sessao.sessao ?? sessao.arquivos[0] ?? 'Sessão'
  return quando ? `${nome} · ${quando}` : nome
}

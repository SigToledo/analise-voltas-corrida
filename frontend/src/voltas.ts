// Regras de exibição dos TIPOS de volta (o tipo em si vem do backend —
// app/metrics/tipos_volta.py). Funções puras, testadas em voltas.test.ts.

import type { MetricasPiloto, TipoVolta, VoltaLeitura } from './types'

/** Tipos que viram ponto na linha do gráfico: as voltas lançadas. */
export const TIPOS_PLOTADOS: readonly TipoVolta[] = ['normal', 'relargada']

export const NOME_TIPO: Record<TipoVolta, string> = {
  normal: 'lançada',
  largada: 'largada',
  saida_box: 'saída do box',
  entrada_box: 'entrada no box',
  safety_car: 'Safety Car',
  relargada: 'relargada',
}

/**
 * Letra na faixa de marcadores do gráfico. Essas voltas não viram ponto na
 * linha (o tempo não representa o ritmo), mas o MOMENTO em que aconteceram
 * é informação real — a letra mostra o quando, sem inventar o quanto.
 */
export const SIGLA_TIPO: Partial<Record<TipoVolta, string>> = {
  entrada_box: 'P',
  saida_box: 'S',
  largada: 'L',
}

export interface FaixaVoltas {
  numero: number
  de: number
  ate: number
}

/**
 * Faixa de voltas de cada Safety Car, olhando só os carros selecionados: um
 * retardatário está uma volta atrás do líder, então "voltas 10–13" do líder
 * podem ser 9–12 dele. A faixa cobre as voltas de SC de todos os selecionados.
 */
export function faixasSafetyCar(
  voltasPorCarro: Record<string, VoltaLeitura[]>,
  carros: string[],
): FaixaVoltas[] {
  const porPeriodo = new Map<number, number[]>()
  for (const carro of carros) {
    for (const v of voltasPorCarro[carro] ?? []) {
      if (v.neutralizacao === null) continue
      const lista = porPeriodo.get(v.neutralizacao) ?? []
      lista.push(v.numero_volta)
      porPeriodo.set(v.neutralizacao, lista)
    }
  }
  return [...porPeriodo.entries()]
    .sort(([a], [b]) => a - b)
    .map(([numero, voltas]) => ({ numero, de: Math.min(...voltas), ate: Math.max(...voltas) }))
}

/**
 * Colunas da tabela de ritmo por trecho: só os trechos em que algum
 * selecionado tem voltas de ritmo (ex.: o trecho da largada até o 1º SC
 * pode não ter nenhuma), com a faixa de voltas que eles cobrem.
 */
export function colunasTrecho(pilotos: MetricasPiloto[]): FaixaVoltas[] {
  const porTrecho = new Map<number, number[]>()
  for (const p of pilotos) {
    for (const t of p.ritmo_por_trecho) {
      porTrecho.set(t.trecho, [...(porTrecho.get(t.trecho) ?? []), ...t.voltas])
    }
  }
  return [...porTrecho.entries()]
    .sort(([a], [b]) => a - b)
    .map(([numero, voltas]) => ({ numero, de: Math.min(...voltas), ate: Math.max(...voltas) }))
}

/** "volta 2" ou "voltas 2–4" (null se não houver número). */
export function rotuloVoltas(de: number | null, ate: number | null): string {
  if (de === null || ate === null) return 'voltas —'
  return de === ate ? `volta ${de}` : `voltas ${de}–${ate}`
}

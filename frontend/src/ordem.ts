// Ordem dos pilotos na tela (chips, legenda, tabelas, cores).
//
// Treino e qualy: melhor volta primeiro (é o que decide a sessão).
// Corrida: a CLASSIFICAÇÃO FINAL do resultado oficial (RaceFull), quando
// enviado — na corrida quem vence é quem chega na frente, não quem fez a
// volta mais rápida. Sem posição oficial, cai para a melhor volta.

import type { MetricasPiloto, Modo } from './types'

function porMelhorVolta(a: MetricasPiloto, b: MetricasPiloto): number {
  if (a.melhor_volta_s === null && b.melhor_volta_s === null) return 0
  if (a.melhor_volta_s === null) return 1
  if (b.melhor_volta_s === null) return -1
  return a.melhor_volta_s - b.melhor_volta_s
}

export function compararPilotos(modo: Modo): (a: MetricasPiloto, b: MetricasPiloto) => number {
  if (modo !== 'corrida') return porMelhorVolta
  return (a, b) => {
    const pa = a.posicao_oficial
    const pb = b.posicao_oficial
    if (pa !== null && pb !== null) return pa - pb
    if (pa !== null) return -1 // classificado antes de não classificado
    if (pb !== null) return 1
    return porMelhorVolta(a, b)
  }
}

// Ordem dos pilotos na tela (chips, legenda, tabelas, cores).
//
// Treino e qualy: melhor volta primeiro (é o que decide a sessão).
// Corrida: a CLASSIFICAÇÃO FINAL do resultado oficial (RaceFull), quando
// enviado — na corrida quem vence é quem chega na frente, não quem fez a
// volta mais rápida. Sem posição oficial, cai para a melhor volta.
// Em qualquer modo, quem tem STATUS oficial (DQ = desclassificado) vai para o
// fim, como no resultado oficial — e nunca é um dos pré-selecionados.

import type { MetricasPiloto, Modo } from './types'

function porMelhorVolta(a: MetricasPiloto, b: MetricasPiloto): number {
  if (a.melhor_volta_s === null && b.melhor_volta_s === null) return 0
  if (a.melhor_volta_s === null) return 1
  if (b.melhor_volta_s === null) return -1
  return a.melhor_volta_s - b.melhor_volta_s
}

function porResultado(a: MetricasPiloto, b: MetricasPiloto): number {
  const pa = a.posicao_oficial
  const pb = b.posicao_oficial
  if (pa !== null && pb !== null) return pa - pb
  if (pa !== null) return -1 // classificado antes de não classificado
  if (pb !== null) return 1
  return porMelhorVolta(a, b)
}

export function compararPilotos(modo: Modo): (a: MetricasPiloto, b: MetricasPiloto) => number {
  const dentro = modo === 'corrida' ? porResultado : porMelhorVolta
  return (a, b) => {
    const sa = a.status_oficial !== null
    const sb = b.status_oficial !== null
    if (sa !== sb) return sa ? 1 : -1
    return dentro(a, b)
  }
}

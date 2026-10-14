import { describe, expect, it } from 'vitest'
import { compararPilotos } from './ordem'
import type { MetricasPiloto } from './types'

const p = (carro: string, melhor: number | null, posicao: number | null, status: string | null = null) =>
  ({
    numero_carro: carro,
    melhor_volta_s: melhor,
    posicao_oficial: posicao,
    status_oficial: status,
  }) as MetricasPiloto

const grid = [p('7', 77.5, 2), p('9', 77.1, 3), p('77', 77.3, 1), p('5', 76.9, null), p('0', null, null)]

describe('compararPilotos', () => {
  it('treino/qualy: melhor volta primeiro, sem volta no fim', () => {
    expect([...grid].sort(compararPilotos('treino')).map((x) => x.numero_carro)).toEqual([
      '5', '9', '77', '7', '0',
    ])
  })

  it('corrida: classificação oficial; não classificados depois, pela melhor volta', () => {
    expect([...grid].sort(compararPilotos('corrida')).map((x) => x.numero_carro)).toEqual([
      '77', '7', '9', '5', '0',
    ])
  })

  it('desclassificado (DQ) vai para o fim em qualquer modo, mesmo com a melhor volta', () => {
    const comDq = [...grid, p('16', 76.0, null, 'DQ')]
    for (const modo of ['treino', 'qualy', 'corrida'] as const) {
      expect([...comDq].sort(compararPilotos(modo)).at(-1)?.numero_carro).toBe('16')
    }
  })
})

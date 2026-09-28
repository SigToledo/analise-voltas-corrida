import { describe, expect, it } from 'vitest'
import { compararPilotos } from './ordem'
import type { MetricasPiloto } from './types'

const p = (carro: string, melhor: number | null, posicao: number | null) =>
  ({ numero_carro: carro, melhor_volta_s: melhor, posicao_oficial: posicao }) as MetricasPiloto

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
})

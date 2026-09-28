import { describe, expect, it } from 'vitest'
import type { MetricasPiloto, VoltaLeitura } from './types'
import { colunasTrecho, faixasSafetyCar, rotuloVoltas } from './voltas'

function volta(n: number, neutralizacao: number | null): VoltaLeitura {
  return {
    numero_volta: n,
    eh_volta_pit: false,
    eh_volta_saida_box: false,
    tempo_volta_s: 80,
    melhor_oficial: false,
    setores_s: [20, 40, 20],
    velocidade_radar_kmh: null,
    campos_ausentes: [],
    tipo: neutralizacao === null ? 'normal' : 'safety_car',
    neutralizacao,
    trecho: neutralizacao === null ? 1 : null,
  }
}

describe('faixasSafetyCar', () => {
  it('cobre as voltas de SC de todos os selecionados (retardatário tem outra numeração)', () => {
    const voltas = {
      '77': [1, 2, 3, 4, 5].map((n) => volta(n, n === 3 || n === 4 ? 1 : null)),
      '9': [1, 2, 3, 4].map((n) => volta(n, n === 2 || n === 3 ? 1 : null)),
      '5': [1, 2].map((n) => volta(n, null)),
    }
    expect(faixasSafetyCar(voltas, ['77', '9'])).toEqual([{ numero: 1, de: 2, ate: 4 }])
    expect(faixasSafetyCar(voltas, ['77'])).toEqual([{ numero: 1, de: 3, ate: 4 }])
    expect(faixasSafetyCar(voltas, ['5'])).toEqual([])
  })
})

describe('colunasTrecho', () => {
  it('só os trechos com voltas de ritmo, na ordem, com a faixa de voltas', () => {
    const p = (ritmo: [number, number[]][]) =>
      ({
        ritmo_por_trecho: ritmo.map(([trecho, voltas]) => ({
          trecho,
          voltas,
          mediana_s: 80,
          poucas_voltas: voltas.length < 4,
        })),
      }) as MetricasPiloto
    const colunas = colunasTrecho([p([[3, [14, 15, 16]], [2, [5, 6]]]), p([[2, [6, 7, 8]]])])
    expect(colunas).toEqual([
      { numero: 2, de: 5, ate: 8 },
      { numero: 3, de: 14, ate: 16 },
    ])
  })
})

describe('rotuloVoltas', () => {
  it('singular, plural e sem número', () => {
    expect(rotuloVoltas(2, 2)).toBe('volta 2')
    expect(rotuloVoltas(10, 13)).toBe('voltas 10–13')
    expect(rotuloVoltas(null, null)).toBe('voltas —')
  })
})

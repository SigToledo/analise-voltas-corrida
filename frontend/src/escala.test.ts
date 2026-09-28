import { describe, expect, it } from 'vitest'
import { marcasEixo, passoMarcadores } from './escala'

describe('marcasEixo', () => {
  it('valores redondos, no máximo 6 marcas', () => {
    expect(marcasEixo(75.3, 80.1)).toEqual([76, 77, 78, 79, 80])
    expect(marcasEixo(77.2, 106)).toEqual([80, 85, 90, 95, 100, 105])
    expect(marcasEixo(79.1, 80.2)).toEqual([79.2, 79.4, 79.6, 79.8, 80, 80.2])
  })

  it('escala vazia não gera marcas', () => {
    expect(marcasEixo(80, 80)).toEqual([])
  })
})

describe('passoMarcadores', () => {
  it('cresce com a escala, com um mínimo', () => {
    expect(passoMarcadores(76, 80)).toBeCloseTo(0.35)
    expect(passoMarcadores(76, 106)).toBeCloseTo(1.8)
  })
})

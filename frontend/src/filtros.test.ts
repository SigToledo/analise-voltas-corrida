import { describe, expect, it } from 'vitest'
import { aplicarFiltros, classesDaSessao, SEM_FILTRO } from './filtros'
import type { MetricasPiloto } from './types'

const p = (carro: string, grupo: string | null, classe: string | null) =>
  ({ numero_carro: carro, grupo, classe }) as MetricasPiloto

// Turma G1 do classificatório da MBR mistura as três classes.
const pilotos = [
  p('171', 'G1', 'ELITE'),
  p('96', 'G1', 'MASTER'),
  p('98', 'G1', 'SUPER'),
  p('7', 'G2', 'SUPER'),
  p('55', 'G2', null),
]

const carros = (lista: MetricasPiloto[]) => lista.map((x) => x.numero_carro)

describe('aplicarFiltros', () => {
  it('sem filtro, todos', () => {
    expect(aplicarFiltros(pilotos, SEM_FILTRO)).toHaveLength(5)
  })

  it('por classe, de qualquer grupo', () => {
    expect(carros(aplicarFiltros(pilotos, { grupo: null, classe: 'SUPER' }))).toEqual(['98', '7'])
  })

  it('grupo e classe juntos', () => {
    expect(carros(aplicarFiltros(pilotos, { grupo: 'G1', classe: 'SUPER' }))).toEqual(['98'])
  })

  it('piloto sem classe só aparece sem filtro de classe', () => {
    expect(carros(aplicarFiltros(pilotos, { grupo: 'G2', classe: null }))).toEqual(['7', '55'])
  })
})

describe('classesDaSessao', () => {
  it('conta cada classe; sem classe não entra', () => {
    expect(classesDaSessao(pilotos)).toEqual([
      { classe: 'ELITE', num_pilotos: 1 },
      { classe: 'MASTER', num_pilotos: 1 },
      { classe: 'SUPER', num_pilotos: 2 },
    ])
  })

  it('sem resumo, nenhuma classe', () => {
    expect(classesDaSessao([p('1', null, null)])).toEqual([])
  })
})

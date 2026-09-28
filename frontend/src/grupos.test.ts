import { describe, expect, it } from 'vitest'
import { avisoGruposMisturados, filtrarPorGrupo, horaDoGrupo } from './grupos'
import type { GrupoSessao, MetricasPiloto } from './types'

const p = (carro: string, grupo: string | null) => ({ numero_carro: carro, grupo }) as MetricasPiloto
const pilotos = [p('171', 'G1'), p('1', 'G1'), p('7', 'G2')]
const grupos: GrupoSessao[] = [
  { sigla: 'G1', rotulo: 'GRUPO 1', sessao: null, data_hora: '11/09/2026 08:45', arquivo: 'a', num_pilotos: 2 },
  { sigla: 'G2', rotulo: 'GRUPO 2', sessao: null, data_hora: '11/09/2026 9:10', arquivo: 'b', num_pilotos: 1 },
]

describe('filtrarPorGrupo', () => {
  it('todos ou só o grupo escolhido', () => {
    expect(filtrarPorGrupo(pilotos, null)).toHaveLength(3)
    expect(filtrarPorGrupo(pilotos, 'G2').map((x) => x.numero_carro)).toEqual(['7'])
  })
})

describe('horaDoGrupo', () => {
  it('formata a hora e completa o zero', () => {
    expect(horaDoGrupo('11/09/2026 08:45')).toBe('08h45')
    expect(horaDoGrupo('11/09/2026 9:10')).toBe('09h10')
    expect(horaDoGrupo(null)).toBeNull()
  })
})

describe('avisoGruposMisturados', () => {
  it('só avisa quando a comparação mistura grupos', () => {
    expect(avisoGruposMisturados(grupos, pilotos, ['171', '1'])).toBeNull()
    expect(avisoGruposMisturados(grupos, pilotos, ['171', '7'])).toBe(
      'Pilotos de grupos diferentes (G1 às 08h45 · G2 às 09h10): a pista pode ter mudado entre um grupo e outro.',
    )
  })
})

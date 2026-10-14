import { describe, expect, it } from 'vitest'
import { rotuloSessao } from './sessoes'
import type { SessaoDisponivel } from './types'

const s = (sessao: string | null, data_hora: string | null): SessaoDisponivel => ({
  chave: `${sessao} | ${data_hora}`,
  sessao,
  data_hora,
  tipo_sessao: 'qualy',
  num_pilotos: 10,
  arquivos: ['RESULTADO.pdf (pág. 2–3)'],
})

describe('rotuloSessao', () => {
  it('nome e hora quando as sessões são do mesmo dia', () => {
    const classif = s('CLASSIFICATORIO - FT', '10/10/2026 13:40')
    const top = s('TOP QUALIFYING - FT', '10/10/2026 14:10')
    expect(rotuloSessao(classif, [classif, top])).toBe('CLASSIFICATORIO - FT · 13:40')
    expect(rotuloSessao(top, [classif, top])).toBe('TOP QUALIFYING - FT · 14:10')
  })

  it('põe a data quando as sessões são de dias diferentes', () => {
    const sexta = s('1º TREINO OFICIAL MBR - GRUPO 1', '11/09/2026 8:45')
    const sabado = s('4º TREINO OFICIAL MBR - GRUPO 1', '12/09/2026 08:00')
    expect(rotuloSessao(sexta, [sexta, sabado])).toBe('1º TREINO OFICIAL MBR - GRUPO 1 · 11/09 08:45')
  })

  it('sem nome nem horário no PDF, usa o arquivo', () => {
    const sem = s(null, null)
    expect(rotuloSessao(sem, [sem])).toBe('RESULTADO.pdf (pág. 2–3)')
  })
})

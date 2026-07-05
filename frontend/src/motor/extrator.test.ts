/**
 * Testes da extração (etapa 1 do motor TS), contra o PDF REAL de samples/.
 *
 * O que está em jogo aqui é a fundação do porte: se a extração devolve as
 * palavras certas, limpas do falso negrito e com coordenadas coerentes, o
 * parser (etapa 2) consegue reproduzir o gabarito do backend Python.
 * Pulados se os PDFs reais não estiverem presentes (não vão para o Git).
 */

import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { extrairPaginas } from './extrator'

const PDF_LAPTIMES = join(
  __dirname,
  '..', '..', '..',
  'samples',
  'MBR - 4o TREINO OFICIAL MBR - GRUPO 1 - Laptimes_sec4.pdf',
)

const temPdf = existsSync(PDF_LAPTIMES)

describe.skipIf(!temPdf)('extrator (PDF real Laptimes)', async () => {
  const bytes = new Uint8Array(readFileSync(PDF_LAPTIMES))
  const paginas = await extrairPaginas(bytes)
  const pag1 = paginas[0]

  it('lê as 3 páginas do relatório', () => {
    expect(paginas).toHaveLength(3)
  })

  it('encontra o cabeçalho do piloto e o cabeçalho da tabela', () => {
    const textos = pag1.palavras.map((p) => p.texto)
    expect(textos).toContain('(171)')
    expect(textos).toContain('L.JOSE')
    expect(textos).toContain('SSTRAP')
  })

  it('lê tempos conhecidos sem corrupção do falso negrito', () => {
    const textos = pag1.palavras.map((p) => p.texto)
    // 2:23.983 = volta 1 do L.JOSE; 48.415 e 2:16.435 são valores em NEGRITO
    // no PDF (impressos 4x) — têm de aparecer limpos e UMA vez só.
    expect(textos).toContain('2:23.983')
    expect(textos.filter((t) => t === '48.415')).toHaveLength(1)
    expect(textos.filter((t) => t === '2:16.435')).toHaveLength(1)
  })

  it('nenhuma palavra sai corrompida (dígitos quadruplicados do falso negrito)', () => {
    // Corrupção típica sem o tratamento: "44448888..." — quatro cópias do
    // mesmo dígito coladas. Nenhuma palavra numérica legítima tem isso.
    const corrompidas = pag1.palavras.filter((p) => /(\d)\1{3}/.test(p.texto))
    expect(corrompidas).toEqual([])
  })

  it('coordenadas coerentes: cabeçalho acima das voltas, colunas esq/dir separadas', () => {
    const cab = pag1.palavras.find((p) => p.texto === '(171)')!
    const sstraps = pag1.palavras.filter((p) => p.texto === 'SSTRAP')
    expect(sstraps.length).toBeGreaterThanOrEqual(2) // uma por coluna de pilotos
    // o cabeçalho da tabela vem ANTES (mais acima) do bloco do primeiro piloto
    expect(Math.min(...sstraps.map((s) => s.top))).toBeLessThan(cab.top)
    // e existe conteúdo nas duas metades da página (coluna esquerda e direita)
    const esq = pag1.palavras.filter((p) => p.x0 < pag1.largura / 2)
    const dir = pag1.palavras.filter((p) => p.x0 >= pag1.largura / 2)
    expect(esq.length).toBeGreaterThan(50)
    expect(dir.length).toBeGreaterThan(50)
  })

  it('o "p" de pit separado do número continua detectável (caso 411/p7)', () => {
    // No PDF real, a p7 do carro 411 vem como "p" + "7" separados ou "p7"
    // junto — o parser trata os dois; aqui garantimos que o texto existe.
    const temP7Junto = pag1.palavras.some((p) => p.texto === 'p7')
    const temPSolto = pag1.palavras.some((p) => p.texto === 'p')
    expect(temP7Junto || temPSolto).toBe(true)
  })
})

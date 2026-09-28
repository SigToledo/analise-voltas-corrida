import { describe, expect, it } from 'vitest'
import { formatarDelta, formatarRelogio, formatarTempo } from './format'

describe('formatarTempo', () => {
  it('formato de cronômetro', () => {
    expect(formatarTempo(134.353)).toBe('2:14.353')
    expect(formatarTempo(124.16)).toBe('2:04.160')
    expect(formatarTempo(49.98)).toBe('49.980')
    expect(formatarTempo(null)).toBe('—')
  })

  it('arredonda antes de separar os minutos (nunca "1:60.000")', () => {
    expect(formatarTempo(119.9996)).toBe('2:00.000')
    expect(formatarTempo(59.9996)).toBe('1:00.000')
  })
})

describe('formatarDelta e formatarRelogio', () => {
  it('sinal e relógio de prova', () => {
    expect(formatarDelta(0.342)).toBe('+0.342')
    expect(formatarDelta(-0.1)).toBe('-0.100')
    expect(formatarRelogio(918.4)).toBe('15:18')
    expect(formatarRelogio(65)).toBe('1:05')
  })
})

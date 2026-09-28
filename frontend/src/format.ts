// Funções de formatação de tempo. Internamente tudo é segundos (float);
// para o engenheiro a gente exibe no formato de cronômetro.

/** 134.353 -> "2:14.353" ; 49.98 -> "49.980". null -> "—". */
export function formatarTempo(segundos: number | null | undefined): string {
  if (segundos === null || segundos === undefined) return '—'
  // Arredonda em milésimos ANTES de separar os minutos: senão 119.9996
  // viraria "1:60.000".
  const milesimos = Math.round(segundos * 1000)
  const minutos = Math.floor(milesimos / 60000)
  const resto = (milesimos - minutos * 60000) / 1000
  if (minutos > 0) {
    // resto precisa de zero à esquerda: 2:04.160, não 2:4.160
    return `${minutos}:${resto.toFixed(3).padStart(6, '0')}`
  }
  return resto.toFixed(3)
}

/** Relógio de prova, sem milésimos: 918.4 -> "15:18". */
export function formatarRelogio(segundos: number): string {
  const s = Math.floor(segundos)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** Diferença com sinal, ex: +0.342 ou -0.100. null -> "—". */
export function formatarDelta(segundos: number | null | undefined): string {
  if (segundos === null || segundos === undefined) return '—'
  const sinal = segundos >= 0 ? '+' : '-'
  return `${sinal}${Math.abs(segundos).toFixed(3)}`
}

/** Percentual com sinal e 2 casas, ex: +1.41%. null -> "—". */
export function formatarPct(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return '—'
  const sinal = pct >= 0 ? '+' : '-'
  return `${sinal}${Math.abs(pct).toFixed(2)}%`
}

/** Velocidade de radar: 184.3 -> "184,3 km/h" (vírgula, padrão BR). null -> "—". */
export function formatarVelocidade(kmh: number | null | undefined): string {
  if (kmh === null || kmh === undefined) return '—'
  return `${kmh.toFixed(1).replace('.', ',')} km/h`
}

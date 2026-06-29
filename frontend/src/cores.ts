// Atribui uma cor fixa a cada piloto selecionado (até 4), na ordem de
// seleção. Usadas no gráfico e nos chips para o olho associar rápido.
export const PALETA = ['var(--p1)', 'var(--p2)', 'var(--p3)', 'var(--p4)']

export function corDoPiloto(selecionados: string[], numeroCarro: string): string {
  const i = selecionados.indexOf(numeroCarro)
  return i >= 0 ? PALETA[i % PALETA.length] : 'var(--texto-fraco)'
}

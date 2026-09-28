import { corDoPiloto } from '../cores'
import { formatarDelta, formatarTempo } from '../format'
import type { AnaliseSessao, MetricasPiloto } from '../types'
import { colunasTrecho, rotuloVoltas } from '../voltas'

interface Props {
  analise: AnaliseSessao
  selecionados: string[]
}

/**
 * Mediana das voltas lançadas em cada TRECHO da sessão:
 * - corrida: cada intervalo de bandeira verde entre Safety Cars (o SC
 *   reagrupa o grid, então comparar o ritmo por trecho é mais justo que a
 *   corrida inteira);
 * - treino: cada saída do box (compara o carro antes e depois de um ajuste).
 * A melhor mediana de cada coluna fica em verde; as outras mostram a
 * diferença para ela.
 */
export function RitmoPorTrecho({ analise, selecionados }: Props) {
  const corrida = analise.modo === 'corrida'
  const pilotos = selecionados
    .map((c) => analise.pilotos.find((p) => p.numero_carro === c))
    .filter((p): p is MetricasPiloto => !!p)
  const colunas = colunasTrecho(pilotos)

  // Melhor mediana de cada coluna (referência verde).
  const melhorPorTrecho = new Map<number, number>()
  for (const col of colunas) {
    const medianas = pilotos
      .map((p) => p.ritmo_por_trecho.find((t) => t.trecho === col.numero)?.mediana_s ?? null)
      .filter((m): m is number => m !== null)
    if (medianas.length) melhorPorTrecho.set(col.numero, Math.min(...medianas))
  }
  const temPoucas = pilotos.some((p) => p.ritmo_por_trecho.some((t) => t.poucas_voltas))

  return (
    <div className="secao">
      <h2>{corrida ? 'Ritmo entre Safety Cars' : 'Ritmo por saída do box'}</h2>
      <p className="status" style={{ textAlign: 'left', fontSize: '0.85rem', marginTop: 0 }}>
        {corrida
          ? 'Mediana das voltas lançadas de cada trecho de bandeira verde — largada, voltas de Safety Car e relargadas ficam de fora.'
          : 'Mediana das voltas lançadas de cada ida à pista — compare o carro antes e depois de um ajuste.'}
      </p>
      {colunas.length === 0 ? (
        <p className="status">Nenhum selecionado tem voltas lançadas para comparar por trecho.</p>
      ) : (
        <div className="tabela-rolavel">
          <table className="dados">
            <thead>
              <tr>
                <th>Piloto</th>
                {colunas.map((col) => (
                  <th key={col.numero}>
                    {corrida ? rotuloVoltas(col.de, col.ate) : `Saída ${col.numero}`}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pilotos.map((p) => (
                <tr key={p.numero_carro}>
                  <td style={{ color: corDoPiloto(selecionados, p.numero_carro) }}>
                    ({p.numero_carro}) {p.nome}
                  </td>
                  {colunas.map((col) => {
                    const t = p.ritmo_por_trecho.find((x) => x.trecho === col.numero)
                    if (!t || t.mediana_s === null) {
                      return (
                        <td key={col.numero} className="sem-leitura">
                          —
                        </td>
                      )
                    }
                    const ref = melhorPorTrecho.get(col.numero) ?? null
                    const delta = ref !== null ? t.mediana_s - ref : null
                    const eRef = delta !== null && delta <= 0.0005
                    return (
                      <td key={col.numero} className={`num${t.poucas_voltas ? ' indicio' : ''}`}>
                        <span className={eRef && pilotos.length > 1 ? 'melhor' : ''}>
                          {formatarTempo(t.mediana_s)}
                          {t.poucas_voltas && '*'}
                        </span>
                        <div className="sub">
                          {eRef || delta === null ? '' : `${formatarDelta(delta)} · `}
                          {corrida
                            ? `${t.voltas.length} v.`
                            : `${rotuloVoltas(Math.min(...t.voltas), Math.max(...t.voltas))}`}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {temPoucas && (
        <p className="status" style={{ textAlign: 'left', fontSize: '0.8rem', marginTop: 0 }}>
          * menos de 4 voltas lançadas no trecho — vale como indício, não como ritmo firme.
        </p>
      )}
    </div>
  )
}

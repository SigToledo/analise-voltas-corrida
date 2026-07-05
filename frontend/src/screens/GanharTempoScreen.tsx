import { corDoPiloto } from '../cores'
import { formatarDelta, formatarPct, formatarTempo } from '../format'
import type { AnaliseSessao, MetricasPiloto } from '../types'

interface Props {
  analise: AnaliseSessao
  selecionados: string[]
}

const SETORES = [1, 2, 3] as const

/** Pega o melhor tempo de um setor (1,2,3) das métricas do piloto. */
function melhorSetor(p: MetricasPiloto, setor: number): number | null {
  if (setor === 1) return p.melhor_setor1_s
  if (setor === 2) return p.melhor_setor2_s
  return p.melhor_setor3_s
}

/** Classe de cor do TEXTO pela magnitude do gap (maior gap = mais "quente"). */
function classeGap(gap: number | null): string {
  if (gap === null) return ''
  if (gap <= 0.001) return 'gap-0'
  if (gap < 0.15) return 'gap-1'
  if (gap < 0.4) return 'gap-2'
  return 'gap-3'
}

/**
 * Cor de FUNDO da célula proporcional ao gap dentro do setor (mapa de calor de
 * verdade): referência fica verde suave; quanto maior o gap em relação ao
 * maior gap daquele setor, mais saturado o laranja/vermelho. Sob luz de
 * garagem, o preenchimento salta mais aos olhos que só a cor do texto.
 */
function fundoGap(gap: number | null, maxGapSetor: number): string {
  if (gap === null) return 'transparent'
  if (gap <= 0.001) return 'var(--verde-fundo)' // referência (mais rápido do grupo)
  const razao = maxGapSetor > 0 ? Math.min(1, gap / maxGapSetor) : 0
  return `rgba(239, 83, 80, ${0.12 + 0.42 * razao})`
}

/**
 * Tela 3 — Onde ganhar tempo.
 * Card da volta ideal da equipe em destaque + mapa de gaps por setor entre os
 * pilotos selecionados. Setor sem leitura aparece como "sem leitura", e o
 * piloto não entra na referência daquele setor.
 */
export function GanharTempoScreen({ analise, selecionados }: Props) {
  const ideal = analise.volta_ideal_equipe
  const pilotos = selecionados
    .map((c) => analise.pilotos.find((p) => p.numero_carro === c))
    .filter((p): p is MetricasPiloto => !!p)

  // Para cada setor, a referência é o menor tempo ENTRE OS SELECIONADOS.
  const refPorSetor: Record<number, number | null> = {}
  for (const s of SETORES) {
    const tempos = pilotos
      .map((p) => melhorSetor(p, s))
      .filter((t): t is number => t !== null)
    refPorSetor[s] = tempos.length ? Math.min(...tempos) : null
  }

  return (
    <div>
      {/* Card volta ideal da equipe */}
      <div className="card-ideal">
        <div className="rotulo">Volta ideal da equipe · melhores setores do grid</div>
        {ideal.total_s === null ? (
          <div className="sem-leitura" style={{ fontSize: '1.4rem' }}>
            Não foi possível montar a volta ideal (algum setor sem leitura no grid).
          </div>
        ) : (
          <div className="total num">{formatarTempo(ideal.total_s)}</div>
        )}
        <div className="setores">
          {SETORES.map((s) => {
            const dono = s === 1 ? ideal.setor1 : s === 2 ? ideal.setor2 : ideal.setor3
            return (
              <div key={s}>
                Setor {s}:{' '}
                {dono.tempo_s === null ? (
                  <span className="sem-leitura">sem leitura</span>
                ) : (
                  <>
                    <b className="num">{formatarTempo(dono.tempo_s)}</b> ({dono.numero_carro_dono}){' '}
                    {dono.nome_dono}
                  </>
                )}
              </div>
            )
          })}
        </div>
        {/* Exclusões/avisos da volta ideal (ex.: setor sem leitura no grid).
            Reforça a regra de não inventar dado: deixa explícito o que ficou
            de fora do cálculo, em vez de mostrar um total "fechado" sem ressalva. */}
        {ideal.avisos.length > 0 && (
          <ul style={{ margin: '0.8rem 0 0', paddingLeft: '1.2rem', fontSize: '0.82rem', color: 'var(--giz-fraco)' }}>
            {ideal.avisos.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        )}
      </div>

      {/* Mapa de gaps por setor entre os selecionados */}
      <div className="secao">
        <h2>Gaps por setor (entre os selecionados)</h2>
        {pilotos.length === 0 ? (
          <p className="status">Selecione pilotos na tela de comparação.</p>
        ) : (
          <div className="tabela-rolavel">
            <table className="dados">
              <thead>
                <tr>
                  <th>Setor</th>
                  {pilotos.map((p) => (
                    <th key={p.numero_carro} style={{ color: corDoPiloto(selecionados, p.numero_carro) }}>
                      ({p.numero_carro})
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {SETORES.map((s) => {
                  const ref = refPorSetor[s]
                  // Maior gap deste setor entre os selecionados, para normalizar
                  // a intensidade do mapa de calor linha a linha.
                  const maxGapSetor = Math.max(
                    0,
                    ...pilotos.map((p) => {
                      const t = melhorSetor(p, s)
                      return t !== null && ref !== null ? t - ref : 0
                    }),
                  )
                  return (
                    <tr key={s}>
                      <td>Setor {s}</td>
                      {pilotos.map((p) => {
                        const t = melhorSetor(p, s)
                        if (t === null) {
                          return (
                            <td key={p.numero_carro} className="sem-leitura">
                              sem leitura
                            </td>
                          )
                        }
                        const gap = ref !== null ? t - ref : null
                        const pct = ref ? ((gap as number) / ref) * 100 : null
                        return (
                          <td
                            key={p.numero_carro}
                            className={`num ${classeGap(gap)}`}
                            style={{ background: fundoGap(gap, maxGapSetor) }}
                          >
                            {formatarTempo(t)}
                            <div style={{ fontSize: '0.78rem' }}>
                              {gap === 0 ? 'referência' : `${formatarDelta(gap)} (${formatarPct(pct)})`}
                            </div>
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="status" style={{ textAlign: 'left', fontSize: '0.85rem' }}>
          Cor mais quente = maior gap = maior oportunidade de ganho naquele setor.
        </p>
      </div>
    </div>
  )
}

import { BarraFiltros } from '../components/Filtros'
import { corDoPiloto } from '../cores'
import type { Filtros } from '../filtros'
import { formatarDelta, formatarPct, formatarTempo } from '../format'
import type { AnaliseSessao, MetricasPiloto, VoltaIdealEquipe } from '../types'

interface Props {
  analise: AnaliseSessao
  selecionados: string[]
  filtros: Filtros
  aoMudarFiltros: (filtros: Filtros) => void
}

/**
 * Card de uma volta ideal (a soma dos melhores setores de um conjunto de
 * pilotos) com o dono de cada setor. `referencia`: o total da volta ideal do
 * grid, para mostrar quanto esta (a de uma classe) está acima dela.
 */
function CardVoltaIdeal({
  titulo,
  ideal,
  numSetores,
  referencia,
}: {
  titulo: string
  ideal: VoltaIdealEquipe
  numSetores: number
  referencia?: number | null
}) {
  const setores = Array.from({ length: numSetores }, (_, i) => i + 1)
  const delta =
    referencia != null && ideal.total_s !== null ? ideal.total_s - referencia : null
  return (
    <div className="card-ideal">
      <div className="rotulo">{titulo}</div>
      {ideal.total_s === null ? (
        <div className="sem-leitura" style={{ fontSize: '1.4rem' }}>
          Não foi possível montar a volta ideal (algum setor sem leitura).
        </div>
      ) : (
        <div className="total num">{formatarTempo(ideal.total_s)}</div>
      )}
      {delta !== null && (
        <div className="delta-ideal num">
          {delta <= 0.0005 ? 'igual à volta ideal do grid' : `${formatarDelta(delta)} da volta ideal do grid`}
        </div>
      )}
      <div className="setores">
        {setores.map((s) => {
          const dono = ideal.setores[s - 1]
          return (
            <div key={s}>
              Setor {s}:{' '}
              {!dono || dono.tempo_s === null ? (
                <span className="sem-leitura">sem leitura</span>
              ) : (
                <>
                  <b className="num">{formatarTempo(dono.tempo_s)}</b> ({dono.numero_carro_dono}){' '}
                  {dono.nome_dono}
                  {dono.grupo_dono && <span className="grupo-legenda"> · {dono.grupo_dono}</span>}
                </>
              )}
            </div>
          )
        })}
      </div>
      {/* Exclusões/avisos da volta ideal (ex.: setor sem leitura). Reforça a
          regra de não inventar dado: deixa explícito o que ficou de fora do
          cálculo, em vez de mostrar um total "fechado" sem ressalva. */}
      {ideal.avisos.length > 0 && (
        <ul style={{ margin: '0.8rem 0 0', paddingLeft: '1.2rem', fontSize: '0.82rem', color: 'var(--giz-fraco)' }}>
          {ideal.avisos.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Melhor tempo do setor (1 = S1…) nas métricas do piloto. */
function melhorSetor(p: MetricasPiloto, setor: number): number | null {
  return p.melhores_setores_s[setor - 1] ?? null
}

/**
 * Cor do TEXTO na célula de gap: só a referência ganha cor (verde); as demais
 * ficam com texto claro neutro. A intensidade da oportunidade é comunicada
 * pelo FUNDO (fundoGap) — texto vermelho sobre fundo vermelho era ilegível.
 */
function classeGap(gap: number | null): string {
  return gap !== null && gap <= 0.001 ? 'gap-0' : ''
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
export function GanharTempoScreen({ analise, selecionados, filtros, aoMudarFiltros }: Props) {
  const ideal = analise.volta_ideal_equipe
  // Com uma classe escolhida, a volta ideal dela aparece AO LADO da do grid:
  // mostra quanto a classe está longe do melhor e o potencial dentro dela.
  const idealClasse = filtros.classe ? analise.voltas_ideais_por_classe[filtros.classe] : undefined
  const grupos = analise.grupos.length > 1 ? ` (${analise.grupos.map((g) => g.sigla).join(' + ')})` : ''
  // Quantos setores a pista tem vem do próprio relatório (3 em Cascavel e
  // Cuiabá, mas pode ser 2 ou 4 em outra pista).
  const SETORES = Array.from({ length: analise.num_setores }, (_, i) => i + 1)
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
      <BarraFiltros analise={analise} filtros={filtros} aoMudar={aoMudarFiltros} mostrarGrupo={false} />

      <div className={idealClasse ? 'ideais lado-a-lado' : 'ideais'}>
        <CardVoltaIdeal
          titulo={`Volta ideal da equipe · melhores setores do grid${grupos}`}
          ideal={ideal}
          numSetores={analise.num_setores}
        />
        {idealClasse && (
          <CardVoltaIdeal
            titulo={`Volta ideal da classe ${filtros.classe} · melhores setores da classe`}
            ideal={idealClasse}
            numSetores={analise.num_setores}
            referencia={ideal.total_s}
          />
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

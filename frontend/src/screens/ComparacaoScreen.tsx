import { useEffect, useState } from 'react'
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { RitmoPorTrecho } from '../components/RitmoPorTrecho'
import { corDoPiloto } from '../cores'
import { LIMITE_JANELA, marcasEixo, passoMarcadores } from '../escala'
import { avisoGruposMisturados, filtrarPorGrupo, horaDoGrupo } from '../grupos'
import { compararPilotos } from '../ordem'
import { formatarDelta, formatarRelogio, formatarTempo, formatarVelocidade } from '../format'
import type { AnaliseSessao, MetricasPiloto, TipoVolta } from '../types'
import { faixasSafetyCar, rotuloVoltas, SIGLA_TIPO, TIPOS_PLOTADOS } from '../voltas'

interface Props {
  analise: AnaliseSessao
  selecionados: string[]
  aoAlternar: (numeroCarro: string) => void
  aoVerGanharTempo: () => void
}

/** Acompanha a largura da janela para adaptar o gráfico em telas estreitas. */
function useLarguraJanela(): number {
  const [largura, setLargura] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth : 1024,
  )
  useEffect(() => {
    const aoRedimensionar = () => setLargura(window.innerWidth)
    window.addEventListener('resize', aoRedimensionar)
    return () => window.removeEventListener('resize', aoRedimensionar)
  }, [])
  return largura
}

const LIMITE_SELECAO = 4

/**
 * Tela 2 — Comparação entre pilotos.
 * Elemento dominante: gráfico de tempo por volta. Só as voltas LANÇADAS
 * viram ponto na linha; largada, box e Safety Car abrem lacuna (valor null,
 * nunca interpolado) e aparecem como letra ou faixa — o momento é real, o
 * tempo não representa o ritmo.
 */
export function ComparacaoScreen({
  analise,
  selecionados,
  aoAlternar,
  aoVerGanharTempo,
}: Props) {
  const estreito = useLarguraJanela() < 640
  const modo = analise.modo
  // Filtro dos chips por grupo (só aparece com grupos juntados). Esconder um
  // grupo não tira da seleção quem já está no gráfico.
  const [filtroGrupo, setFiltroGrupo] = useState<string | null>(null)
  const temGrupos = analise.grupos.length > 1

  // Pilotos na ordem da sessão: melhor volta (treino/qualy) ou resultado
  // oficial (corrida, quando o RaceFull foi enviado). Sem volta vai para o fim.
  const pilotos = [...analise.pilotos].sort(compararPilotos(modo))
  const mostrarPosicao = modo === 'corrida' && pilotos.some((p) => p.posicao_oficial !== null)
  const pilotosVisiveis = filtrarPorGrupo(pilotos, temGrupos ? filtroGrupo : null)
  const avisoGrupos = avisoGruposMisturados(analise.grupos, analise.pilotos, selecionados)

  const metricas = new Map(analise.pilotos.map((p) => [p.numero_carro, p]))
  // Voltas que a cronometragem desconsiderou (mais rápidas que a oficial —
  // canceladas, ex.: limite de pista). Não entram na linha: viram "×".
  const desconsideradas = new Map(
    selecionados.map((c) => [c, new Set(metricas.get(c)?.voltas_desconsideradas ?? [])]),
  )

  // Dados do gráfico: uma linha por volta, com o tempo de cada selecionado
  // (null se a volta não é lançada, foi desconsiderada ou não tem leitura) e
  // o tipo, para o tooltip e o desenho do ponto.
  const maxVolta = Math.max(
    1,
    ...selecionados.flatMap((c) =>
      (analise.voltas_por_carro[c] ?? []).map((v) => v.numero_volta),
    ),
  )
  const dadosGrafico = []
  for (let n = 1; n <= maxVolta; n++) {
    const ponto: Record<string, number | string | null> = { volta: n }
    for (const carro of selecionados) {
      const volta = (analise.voltas_por_carro[carro] ?? []).find((v) => v.numero_volta === n)
      const naLinha =
        volta && TIPOS_PLOTADOS.includes(volta.tipo) && !desconsideradas.get(carro)?.has(n)
      ponto[carro] = naLinha ? volta.tempo_volta_s : null
      ponto[`${carro}#tipo`] = volta?.tipo ?? null
      ponto[`${carro}#melhor`] = metricas.get(carro)?.numero_volta_melhor === n ? 1 : 0
    }
    dadosGrafico.push(ponto)
  }

  // Escala do eixo Y focada nas voltas de ATAQUE. Sem isso, uma única volta
  // lenta (tráfego, desaquecimento no qualy) estica o eixo e espreme todas as
  // voltas boas numa faixa ilegível. A janela usa só voltas lançadas,
  // completas, que não são outlier nem desconsideradas e estão a até 107% da
  // melhor do piloto; o que passar disso continua plotado (a linha sai pelo
  // topo), mas a escala fica útil.
  const temposLimpos: number[] = []
  for (const carro of selecionados) {
    const metr = metricas.get(carro)
    const fora = new Set([
      ...(metr?.voltas_outlier ?? []),
      ...(metr?.voltas_desconsideradas ?? []),
    ])
    const teto = metr?.melhor_volta_s != null ? metr.melhor_volta_s * LIMITE_JANELA : Infinity
    for (const v of analise.voltas_por_carro[carro] ?? []) {
      const completa = v.tempo_volta_s !== null && v.setores_s.every((s) => s !== null)
      if (
        v.tipo === 'normal' &&
        completa &&
        !fora.has(v.numero_volta) &&
        (v.tempo_volta_s as number) <= teto
      ) {
        temposLimpos.push(v.tempo_volta_s as number)
      }
    }
  }
  const temJanela = temposLimpos.length > 0
  const minLimpo = temJanela ? Math.floor(Math.min(...temposLimpos)) - 1 : 0
  const maxLimpo = temJanela ? Math.ceil(Math.max(...temposLimpos)) + 1 : 0
  // Reserva uma faixa no rodapé para os marcadores: uma "linha" por piloto,
  // com altura proporcional à escala para as letras não se encostarem.
  const passo = passoMarcadores(minLimpo, maxLimpo)
  const yDomain: [number, number] | ['auto', 'auto'] = temJanela
    ? [minLimpo - passo * (selecionados.length + 0.4), maxLimpo]
    : ['auto', 'auto']

  // Marcadores por piloto: P (entrou no box), S (saída do box), L
  // (largada) e × (desconsiderada pela cronometragem).
  const marcadores = temJanela
    ? selecionados.map((carro, i) => ({
        carro,
        pontos: (analise.voltas_por_carro[carro] ?? [])
          .map((v) => ({
            volta: v.numero_volta,
            nivel: (yDomain[0] as number) + passo * (0.7 + i),
            simbolo: desconsideradas.get(carro)?.has(v.numero_volta) ? '×' : SIGLA_TIPO[v.tipo],
          }))
          .filter((m) => m.simbolo),
      }))
    : []
  const siglasUsadas = new Set(marcadores.flatMap((m) => m.pontos.map((p) => p.simbolo)))

  // Faixas de Safety Car (só no modo corrida), nas voltas dos selecionados.
  const faixasSC = faixasSafetyCar(analise.voltas_por_carro, selecionados)
  const temRelargada = selecionados.some((c) =>
    (analise.voltas_por_carro[c] ?? []).some((v) => v.tipo === 'relargada'),
  )

  // Para a tabela de melhor volta: o mais rápido entre os SELECIONADOS.
  const melhoresSelecionados = selecionados
    .map((c) => analise.pilotos.find((p) => p.numero_carro === c))
    .filter((p): p is MetricasPiloto => !!p && p.melhor_volta_s !== null)
  const refMelhor =
    melhoresSelecionados.length > 0
      ? Math.min(...melhoresSelecionados.map((p) => p.melhor_volta_s as number))
      : null
  const algumPoucasVoltas = selecionados.some(
    (c) => analise.pilotos.find((p) => p.numero_carro === c)?.poucas_voltas,
  )

  return (
    <div>
      {modo === 'corrida' && <FaixaSafetyCar analise={analise} />}

      <p className="status" style={{ textAlign: 'left', marginTop: 0 }}>
        Clique nos pilotos para comparar (até {LIMITE_SELECAO}).
      </p>

      {/* Filtro por grupo: Todos | G1 | G2 (sessão com grupos juntados). */}
      {temGrupos && (
        <div className="filtro-grupo" role="group" aria-label="Filtrar pilotos por grupo">
          <button
            className={filtroGrupo === null ? 'ativo' : ''}
            aria-pressed={filtroGrupo === null}
            onClick={() => setFiltroGrupo(null)}
          >
            Todos <small>{analise.num_pilotos}</small>
          </button>
          {analise.grupos.map((g) => (
            <button
              key={g.sigla}
              className={filtroGrupo === g.sigla ? 'ativo' : ''}
              aria-pressed={filtroGrupo === g.sigla}
              title={g.sessao ?? g.rotulo}
              onClick={() => setFiltroGrupo(g.sigla)}
            >
              {g.sigla}
              <small>
                {g.num_pilotos}
                {horaDoGrupo(g.data_hora) && ` · ${horaDoGrupo(g.data_hora)}`}
              </small>
            </button>
          ))}
        </div>
      )}

      {/* Chips de seleção */}
      <div className="chips">
        {pilotosVisiveis.map((p) => {
          const sel = selecionados.includes(p.numero_carro)
          const cor = corDoPiloto(selecionados, p.numero_carro)
          return (
            <button
              key={p.numero_carro}
              className={`chip${sel ? ' selecionado' : ''}`}
              style={{ borderColor: sel ? cor : 'var(--risco)' }}
              onClick={() => aoAlternar(p.numero_carro)}
              disabled={!sel && selecionados.length >= LIMITE_SELECAO}
            >
              <span className="nome">
                {sel && <i className="ponto" style={{ background: cor }} />}
                {mostrarPosicao && (
                  <span className="posicao num">
                    {p.posicao_oficial !== null ? `P${p.posicao_oficial}` : 'NC'}
                  </span>
                )}
                ({p.numero_carro}) {p.nome}
                {p.classe && <span className="classe">{p.classe}</span>}
                {temGrupos && p.grupo && <span className="grupo">{p.grupo}</span>}
              </span>
              <span className="tempo num">{formatarTempo(p.melhor_volta_s)}</span>
            </button>
          )
        })}
      </div>

      {/* Legenda cor → piloto (o gráfico sozinho não diz qual cor é quem). */}
      {selecionados.length > 0 && (
        <div className="legenda">
          {selecionados.map((carro) => {
            const p = analise.pilotos.find((x) => x.numero_carro === carro)
            return (
              <span key={carro}>
                <i style={{ background: corDoPiloto(selecionados, carro) }} />(
                {carro}) {p?.nome}
                {temGrupos && p?.grupo && <small className="grupo-legenda"> {p.grupo}</small>}
              </span>
            )
          })}
        </div>
      )}
      {avisoGrupos && <p className="aviso-grupos">{avisoGrupos}</p>}

      {/* Gráfico de tempo por volta */}
      {selecionados.length === 0 ? (
        <p className="status">Selecione ao menos um piloto para ver o gráfico.</p>
      ) : (
        <div style={{ width: '100%', height: 360 }}>
          <ResponsiveContainer>
            <ComposedChart data={dadosGrafico} margin={{ top: 10, right: 24, bottom: 10, left: 16 }}>
              <CartesianGrid stroke="var(--risco)" strokeDasharray="3 3" />
              <XAxis
                dataKey="volta"
                type="number"
                domain={[1, maxVolta]}
                ticks={Array.from({ length: maxVolta }, (_, i) => i + 1)}
                stroke="var(--giz-fraco)"
                label={{ value: 'Volta', position: 'insideBottom', offset: -2, fill: 'var(--giz-fraco)' }}
              />
              <YAxis
                stroke="var(--giz-fraco)"
                domain={yDomain}
                allowDataOverflow={temJanela}
                ticks={temJanela ? marcasEixo(minLimpo, maxLimpo) : undefined}
                width={estreito ? 64 : 92}
                tick={{ fontSize: estreito ? 11 : 13 }}
                tickFormatter={(s) => formatarTempo(s as number)}
              />
              {/* Faixa amarela = provável Safety Car (desenhada antes das
                  linhas, para ficar atrás delas). */}
              {faixasSC.map((f) => (
                <ReferenceArea
                  key={`sc-${f.numero}`}
                  x1={Math.max(1, f.de - 0.5)}
                  x2={Math.min(maxVolta, f.ate + 0.5)}
                  fill="var(--ambar)"
                  fillOpacity={0.13}
                  stroke="none"
                  ifOverflow="hidden"
                  label={{
                    value: faixasSC.length > 1 ? `SC${f.numero}` : 'SC',
                    position: 'insideTop',
                    fill: 'var(--ambar)',
                    fontSize: 12,
                    fontWeight: 700,
                  }}
                />
              ))}
              <Tooltip
                contentStyle={{ background: 'var(--painel)', border: '1px solid var(--risco)' }}
                labelStyle={{ color: 'var(--giz)' }}
                formatter={(valor, nome, item) => {
                  const dados = item?.payload as Record<string, unknown> | undefined
                  const extra =
                    (dados?.[`${nome}#melhor`] ? ' · melhor volta' : '') +
                    (dados?.[`${nome}#tipo`] === 'relargada' ? ' · relargada' : '')
                  return [`${formatarTempo(valor as number)}${extra}`, `Carro ${nome}`]
                }}
                labelFormatter={(l) => `Volta ${l}`}
              />
              {selecionados.map((carro) => {
                const cor = corDoPiloto(selecionados, carro)
                return (
                  <Line
                    key={carro}
                    type="monotone"
                    dataKey={carro}
                    stroke={cor}
                    strokeWidth={2.5}
                    // Melhor volta: ponto maior com anel claro. Relargada:
                    // círculo vazado (volta lançada, mas logo após o SC —
                    // pneu frio e pelotão junto).
                    dot={(props: {
                      cx?: number
                      cy?: number
                      index?: number
                      payload?: Record<string, unknown>
                    }) => {
                      const chave = `${carro}-${props.index}`
                      if (props.cx == null || props.cy == null || props.payload?.[carro] == null) {
                        return <g key={chave} />
                      }
                      const tipo = props.payload?.[`${carro}#tipo`] as TipoVolta | undefined
                      if (props.payload?.[`${carro}#melhor`]) {
                        return (
                          <circle key={chave} cx={props.cx} cy={props.cy} r={5.5} fill={cor} stroke="var(--giz)" strokeWidth={2} />
                        )
                      }
                      return tipo === 'relargada' ? (
                        <circle key={chave} cx={props.cx} cy={props.cy} r={4} fill="var(--pista)" stroke={cor} strokeWidth={2} />
                      ) : (
                        <circle key={chave} cx={props.cx} cy={props.cy} r={3} fill={cor} stroke={cor} />
                      )
                    }}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                )
              })}
              {/* Marcadores P / S / L na cor do piloto, numa faixa própria no
                  rodapé do gráfico. */}
              {marcadores.map(({ carro, pontos }) => (
                <Scatter
                  key={`marca-${carro}`}
                  data={pontos}
                  dataKey="nivel"
                  isAnimationActive={false}
                  tooltipType="none"
                  shape={(props: { cx?: number; cy?: number; payload?: { simbolo?: string } }) => (
                    <text
                      x={props.cx}
                      y={(props.cy ?? 0) + 4}
                      textAnchor="middle"
                      fontSize={11}
                      fontWeight={700}
                      fontFamily="var(--tipo-tempo)"
                      fill={corDoPiloto(selecionados, carro)}
                    >
                      {props.payload?.simbolo}
                    </text>
                  )}
                />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {selecionados.length > 0 && temJanela && (
        <p className="status legenda-grafico">
          {siglasUsadas.has('L') && (
            <span>
              <b>L</b> largada
            </span>
          )}
          {siglasUsadas.has('P') && (
            <span>
              <b>P</b> entrou no box
            </span>
          )}
          {siglasUsadas.has('S') && (
            <span>
              <b>S</b> saída do box
            </span>
          )}
          {siglasUsadas.has('×') && (
            <span>
              <b>×</b> desconsiderada pela cronometragem
            </span>
          )}
          <span>
            <b className="melhor-ponto">●</b> melhor volta
          </span>
          {faixasSC.length > 0 && (
            <span>
              <b className="sc">SC</b> provável Safety Car
            </span>
          )}
          {temRelargada && (
            <span>
              <b>○</b> relargada
            </span>
          )}
          <span>— só as voltas lançadas viram ponto na linha.</span>
        </p>
      )}

      {/* Resumo dos selecionados: colunas conforme o modo. */}
      <div className="secao" style={{ marginTop: '1.5rem' }}>
        <h2>Resumo dos selecionados</h2>
        <div className="tabela-rolavel">
          <table className="dados">
            <thead>
              <tr>
                <th>Piloto</th>
                <th>Melhor volta</th>
                <th>Volta nº</th>
                <th>Delta</th>
                {modo === 'qualy' ? (
                  <>
                    <th title="Soma dos melhores setores do próprio piloto">Teórica</th>
                    <th title="Melhor volta − teórica: o que ficou na mesa">Na mesa</th>
                  </>
                ) : (
                  <>
                    <th title="Mediana das voltas lançadas (sem largada, box, SC e relargada)">
                      Ritmo (mediana)
                    </th>
                    <th title="Dispersão típica das voltas lançadas (MAD × 1,4826): quanto menor, mais constante">
                      Consistência
                    </th>
                  </>
                )}
                {analise.tem_radar && <th>Radar máx.</th>}
                {analise.tem_radar && modo !== 'qualy' && (
                  <th title="Mediana do radar nas voltas lançadas">Radar mediano</th>
                )}
              </tr>
            </thead>
            <tbody>
              {selecionados.map((carro) => {
                const p = analise.pilotos.find((x) => x.numero_carro === carro)
                if (!p) return null
                const semVolta = p.melhor_volta_s === null
                const delta =
                  refMelhor !== null && p.melhor_volta_s !== null
                    ? p.melhor_volta_s - refMelhor
                    : null
                const indicio = p.poucas_voltas ? ' indicio' : ''
                return (
                  <tr key={carro}>
                    <td style={{ color: corDoPiloto(selecionados, carro) }}>
                      ({p.numero_carro}) {p.nome}
                    </td>
                    {semVolta ? (
                      <td className="sem-leitura" colSpan={2}>
                        — sem volta válida
                      </td>
                    ) : (
                      <>
                        <td className="num melhor">{formatarTempo(p.melhor_volta_s)}</td>
                        <td className="num">{p.numero_volta_melhor ?? '—'}</td>
                      </>
                    )}
                    <td className="num">{delta === 0 ? '—' : formatarDelta(delta)}</td>
                    {modo === 'qualy' ? (
                      <>
                        <td className="num">{formatarTempo(p.melhor_volta_teorica_s)}</td>
                        <td className="num">{formatarDelta(p.gap_real_para_teorica_s)}</td>
                      </>
                    ) : (
                      <>
                        <td className={`num${indicio}`}>
                          {formatarTempo(p.mediana_voltas_limpas_s)}
                          {p.poucas_voltas && p.mediana_voltas_limpas_s !== null && '*'}
                          <div className="sub">{p.num_voltas_limpas} v.</div>
                        </td>
                        <td className={`num${indicio}`}>
                          {p.consistencia_s === null ? '—' : `±${p.consistencia_s.toFixed(3)}`}
                        </td>
                      </>
                    )}
                    {analise.tem_radar && (
                      <td className="num">{formatarVelocidade(p.radar_maximo_kmh)}</td>
                    )}
                    {analise.tem_radar && modo !== 'qualy' && (
                      <td className="num">{formatarVelocidade(p.radar_mediano_kmh)}</td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {modo !== 'qualy' && algumPoucasVoltas && (
          <p className="status" style={{ textAlign: 'left', fontSize: '0.8rem', marginTop: '-0.8rem' }}>
            * menos de 4 voltas lançadas — ritmo e consistência valem como indício.
          </p>
        )}

        <Observacoes analise={analise} selecionados={selecionados} />

        {selecionados.length > 0 && (
          <button className="cta-ganhar" onClick={aoVerGanharTempo}>
            Ver onde ganhar tempo →
          </button>
        )}
      </div>

      {modo !== 'qualy' && selecionados.length > 0 && (
        <RitmoPorTrecho analise={analise} selecionados={selecionados} />
      )}
    </div>
  )
}

/**
 * O que o cálculo precisa que o engenheiro saiba sobre cada selecionado:
 * voltas desconsideradas (com os tempos), setor sem leitura, piloto sem
 * volta oficial. Vem pronto do backend (MetricasPiloto.avisos).
 */
function Observacoes({ analise, selecionados }: { analise: AnaliseSessao; selecionados: string[] }) {
  const itens = selecionados.flatMap((carro) => {
    const p = analise.pilotos.find((x) => x.numero_carro === carro)
    return (p?.avisos ?? []).map((aviso, i) => ({ p: p as MetricasPiloto, aviso, chave: `${carro}-${i}` }))
  })
  if (itens.length === 0) return null
  return (
    <div className="observacoes">
      <h3>Observações</h3>
      <ul>
        {itens.map(({ p, aviso, chave }) => (
          <li key={chave}>
            <b style={{ color: corDoPiloto(selecionados, p.numero_carro) }}>({p.numero_carro})</b>{' '}
            {aviso}
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Aviso dos prováveis Safety Cars da corrida, com voltas e horário. */
function FaixaSafetyCar({ analise }: { analise: AnaliseSessao }) {
  const periodos = analise.neutralizacoes
  return (
    <div className="faixa-sc">
      {periodos.length === 0 ? (
        <span>
          <b>Nenhum Safety Car detectado</b> — em nenhum momento o grid inteiro ficou lento junto.
        </span>
      ) : (
        <>
          <b>
            {periodos.length === 1
              ? '1 provável Safety Car'
              : `${periodos.length} prováveis Safety Cars`}
          </b>
          <ul>
            {periodos.map((p) => (
              <li key={p.numero}>
                SC{p.numero} · {rotuloVoltas(p.volta_inicial_lider, p.volta_final_lider)} do líder · ~
                {formatarRelogio(p.inicio_s)} a ~{formatarRelogio(p.fim_s)} de prova
              </li>
            ))}
          </ul>
          <div className="nota">
            Inferido dos tempos: o PDF não marca Safety Car, mas o grid inteiro fica lento ao mesmo
            tempo (tráfego ou erro afetam um piloto só). Essas voltas, a largada e as relargadas
            ficam fora do ritmo.
          </div>
        </>
      )}
    </div>
  )
}

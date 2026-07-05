import { useEffect, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { corDoPiloto } from '../cores'
import { formatarDelta, formatarTempo, formatarVelocidade } from '../format'
import type { AnaliseSessao, MetricasPiloto } from '../types'

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
 * Elemento dominante: gráfico de tempo por volta. Voltas de pit ou sem
 * leitura viram lacuna no gráfico (valor null) — nunca interpoladas.
 */
export function ComparacaoScreen({
  analise,
  selecionados,
  aoAlternar,
  aoVerGanharTempo,
}: Props) {
  const estreito = useLarguraJanela() < 640

  // Pilotos ordenados por melhor volta (mais rápido primeiro). Quem não tem
  // volta válida vai para o fim.
  const pilotos = [...analise.pilotos].sort(ordenarPorMelhorVolta)

  // Monta os dados do gráfico: uma linha por volta, com o tempo de cada
  // piloto selecionado (ou null se for pit / sem leitura).
  const maxVolta = Math.max(
    1,
    ...selecionados.flatMap((c) =>
      (analise.voltas_por_carro[c] ?? []).map((v) => v.numero_volta),
    ),
  )
  const dadosGrafico = []
  for (let n = 1; n <= maxVolta; n++) {
    const ponto: Record<string, number | null> = { volta: n }
    for (const carro of selecionados) {
      const volta = (analise.voltas_por_carro[carro] ?? []).find((v) => v.numero_volta === n)
      // Pit ou tempo ausente -> null (lacuna no gráfico, sem interpolar).
      ponto[carro] = volta && !volta.eh_volta_pit ? volta.tempo_volta_s : null
    }
    dadosGrafico.push(ponto)
  }

  // Escala do eixo Y focada nas voltas de RITMO. Sem isso, uma única volta
  // lenta (tráfego/saída de box, 4-5 min) estica o eixo e espreme todas as
  // voltas boas numa faixa ilegível no rodapé. Calculamos a janela só com
  // voltas "limpas" (não-pit, completas e não marcadas como outlier); os
  // pontos lentos continuam plotados (a linha sobe e sai pelo topo), mas a
  // escala fica útil para comparar ritmo.
  const temposLimpos: number[] = []
  for (const carro of selecionados) {
    const metr = analise.pilotos.find((p) => p.numero_carro === carro)
    const outliers = new Set(metr?.voltas_outlier ?? [])
    for (const v of analise.voltas_por_carro[carro] ?? []) {
      const completa =
        v.tempo_volta_s !== null &&
        v.setor1_s !== null &&
        v.setor2_s !== null &&
        v.setor3_s !== null
      if (!v.eh_volta_pit && completa && !outliers.has(v.numero_volta)) {
        temposLimpos.push(v.tempo_volta_s as number)
      }
    }
  }
  const temJanela = temposLimpos.length > 0
  const yDomain: [number, number] | ['auto', 'auto'] = temJanela
    ? [Math.floor(Math.min(...temposLimpos)) - 1, Math.ceil(Math.max(...temposLimpos)) + 1]
    : ['auto', 'auto']

  // Para a tabela de melhor volta: o mais rápido entre os SELECIONADOS.
  const melhoresSelecionados = selecionados
    .map((c) => analise.pilotos.find((p) => p.numero_carro === c))
    .filter((p): p is MetricasPiloto => !!p && p.melhor_volta_s !== null)
  const refMelhor =
    melhoresSelecionados.length > 0
      ? Math.min(...melhoresSelecionados.map((p) => p.melhor_volta_s as number))
      : null

  return (
    <div>
      <p className="status" style={{ textAlign: 'left', marginTop: 0 }}>
        Clique nos pilotos para comparar (até {LIMITE_SELECAO}).
      </p>

      {/* Chips de seleção */}
      <div className="chips">
        {pilotos.map((p) => {
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
                ({p.numero_carro}) {p.nome}
                {p.classe && <span className="classe">{p.classe}</span>}
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
              </span>
            )
          })}
        </div>
      )}

      {/* Gráfico de tempo por volta */}
      {selecionados.length === 0 ? (
        <p className="status">Selecione ao menos um piloto para ver o gráfico.</p>
      ) : (
        <div style={{ width: '100%', height: 360 }}>
          <ResponsiveContainer>
            <LineChart data={dadosGrafico} margin={{ top: 10, right: 24, bottom: 10, left: 16 }}>
              <CartesianGrid stroke="var(--risco)" strokeDasharray="3 3" />
              <XAxis
                dataKey="volta"
                stroke="var(--giz-fraco)"
                label={{ value: 'Volta', position: 'insideBottom', offset: -2, fill: 'var(--giz-fraco)' }}
              />
              <YAxis
                stroke="var(--giz-fraco)"
                domain={yDomain}
                allowDataOverflow={temJanela}
                width={estreito ? 64 : 92}
                tick={{ fontSize: estreito ? 11 : 13 }}
                tickFormatter={(s) => formatarTempo(s as number)}
              />
              <Tooltip
                contentStyle={{ background: 'var(--painel)', border: '1px solid var(--risco)' }}
                labelStyle={{ color: 'var(--giz)' }}
                formatter={(valor, nome) => [formatarTempo(valor as number), `Carro ${nome}`]}
                labelFormatter={(l) => `Volta ${l}`}
              />
              {selecionados.map((carro) => (
                <Line
                  key={carro}
                  type="monotone"
                  dataKey={carro}
                  stroke={corDoPiloto(selecionados, carro)}
                  strokeWidth={2.5}
                  dot={{ r: 3 }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Tabela de melhor volta com delta para o mais rápido entre selecionados */}
      <div className="secao" style={{ marginTop: '1.5rem' }}>
        <h2>Melhor volta dos selecionados</h2>
        <div className="tabela-rolavel">
          <table className="dados">
            <thead>
              <tr>
                <th>Piloto</th>
                <th>Melhor volta</th>
                <th>Volta nº</th>
                <th>Delta</th>
                <th>Mediana</th>
                <th>Consistência (s)</th>
                <th>Vel. radar (km/h)</th>
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
                    <td className="num">{formatarTempo(p.mediana_voltas_limpas_s)}</td>
                    <td className="num">
                      {p.consistencia_desvio_padrao_s === null
                        ? '—'
                        : p.consistencia_desvio_padrao_s.toFixed(3)}
                    </td>
                    <td className="num">{formatarVelocidade(p.melhor_sstrap_kmh)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {selecionados.length > 0 && (
          <button className="cta-ganhar" onClick={aoVerGanharTempo}>
            Ver onde ganhar tempo →
          </button>
        )}
      </div>
    </div>
  )
}

function ordenarPorMelhorVolta(a: MetricasPiloto, b: MetricasPiloto): number {
  if (a.melhor_volta_s === null) return 1
  if (b.melhor_volta_s === null) return -1
  return a.melhor_volta_s - b.melhor_volta_s
}

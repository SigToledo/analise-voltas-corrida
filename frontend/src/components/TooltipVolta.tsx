import { corDoPiloto } from '../cores'
import { formatarTempo } from '../format'
import type { AnaliseSessao } from '../types'
import { NOME_TIPO } from '../voltas'

interface Props {
  analise: AnaliseSessao
  selecionados: string[]
  // Preenchidos pelo Recharts ao passar o mouse:
  active?: boolean
  label?: number | string
}

/**
 * Caixa que aparece ao passar o mouse no gráfico: a volta sob o cursor, com
 * o tempo de CADA selecionado — inclusive das voltas que não viram ponto na
 * linha (Safety Car, largada, box, desconsiderada). O tempo é dado real do
 * PDF; ele só não entra no ritmo, e por isso vem com o tipo ao lado.
 * Os dados saem direto da análise (não do que o gráfico desenhou).
 */
export function TooltipVolta({ analise, selecionados, active, label }: Props) {
  const volta = Number(label)
  if (!active || !Number.isFinite(volta)) return null

  return (
    <div className="tooltip-volta">
      <div className="titulo">Volta {volta}</div>
      {selecionados.map((carro) => {
        const metr = analise.pilotos.find((p) => p.numero_carro === carro)
        const v = (analise.voltas_por_carro[carro] ?? []).find((x) => x.numero_volta === volta)
        const marcas: string[] = []
        if (v) {
          if (v.tipo !== 'normal') {
            marcas.push(v.tipo === 'safety_car' && v.neutralizacao ? `Safety Car ${v.neutralizacao}` : NOME_TIPO[v.tipo])
          }
          if (metr?.numero_volta_melhor === volta) marcas.push('melhor volta')
          if (metr?.voltas_desconsideradas.includes(volta)) marcas.push('desconsiderada')
        }
        return (
          <div key={carro} className="linha">
            <i style={{ background: corDoPiloto(selecionados, carro) }} />
            <span className="piloto">({carro})</span>
            {!v ? (
              <span className="sem-leitura">não completou esta volta</span>
            ) : (
              <>
                <b className="num">{v.tempo_volta_s === null ? 'sem leitura' : formatarTempo(v.tempo_volta_s)}</b>
                {marcas.length > 0 && <span className="marca">{marcas.join(' · ')}</span>}
                <span className="setores num">
                  {v.setores_s.map((s, i) => `S${i + 1} ${s === null ? '—' : formatarTempo(s)}`).join('  ')}
                </span>
              </>
            )}
          </div>
        )
      })}
    </div>
  )
}

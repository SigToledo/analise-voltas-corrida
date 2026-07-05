import { useMemo, useState } from 'react'
import './App.css'
import { ComparacaoScreen } from './screens/ComparacaoScreen'
import { GanharTempoScreen } from './screens/GanharTempoScreen'
import { UploadScreen } from './screens/UploadScreen'
import type { AnaliseSessao } from './types'

type Tela = 'upload' | 'comparacao' | 'ganhar'

export default function App() {
  const [analise, setAnalise] = useState<AnaliseSessao | null>(null)
  const [tela, setTela] = useState<Tela>('upload')
  const [selecionados, setSelecionados] = useState<string[]>([])
  const [mostrarAvisos, setMostrarAvisos] = useState(false)

  function aoConcluirUpload(a: AnaliseSessao) {
    setAnalise(a)
    // Pré-seleciona os 2 pilotos mais rápidos (com volta válida).
    const doisMaisRapidos = [...a.pilotos]
      .filter((p) => p.melhor_volta_s !== null)
      .sort((x, y) => (x.melhor_volta_s as number) - (y.melhor_volta_s as number))
      .slice(0, 2)
      .map((p) => p.numero_carro)
    setSelecionados(doisMaisRapidos)
    setTela('comparacao')
  }

  function alternarSelecionado(numeroCarro: string) {
    setSelecionados((atual) =>
      atual.includes(numeroCarro)
        ? atual.filter((c) => c !== numeroCarro)
        : [...atual, numeroCarro],
    )
  }

  // A ordem de exibição NUNCA é a ordem do clique: os selecionados aparecem
  // sempre na posição que fizeram na sessão (melhor volta primeiro). Isso
  // também estabiliza as cores: o mais rápido é sempre a 1ª cor, e assim
  // por diante — legenda, tabelas e gaps ficam na mesma ordem do resultado.
  const selecionadosOrdenados = useMemo(() => {
    if (!analise) return selecionados
    const melhorPorCarro = new Map(
      analise.pilotos.map((p) => [p.numero_carro, p.melhor_volta_s]),
    )
    return [...selecionados].sort((a, b) => {
      const ta = melhorPorCarro.get(a) ?? null
      const tb = melhorPorCarro.get(b) ?? null
      if (ta === null) return 1
      if (tb === null) return -1
      return ta - tb
    })
  }, [analise, selecionados])

  // Sem análise ainda: só a tela de upload.
  if (!analise) {
    return (
      <div className="app">
        <UploadScreen aoConcluir={aoConcluirUpload} />
      </div>
    )
  }

  const meta = analise.metadados

  return (
    <div className="app">
      {/* Faixa de sessão: o cabeçalho do próprio PDF, como num monitor de
          cronometragem. Só mostra o que foi extraído — nada é inventado. */}
      <div className="faixa-sessao">
        <span className="sessao">{meta?.sessao ?? 'Sessão'}</span>
        {meta?.pista && <span className="dado">{meta.pista}</span>}
        {meta?.data_hora && <span className="dado">{meta.data_hora}</span>}
        {meta?.evento && <span className="dado">{meta.evento}</span>}
      </div>

      <div className="topbar">
        <div className="arquivo num">
          {analise.arquivo_origem} · {analise.num_pilotos} pilotos
        </div>
        <div className="nav">
          <div className="nav-tabs">
            <button
              className={tela === 'comparacao' ? 'ativo' : ''}
              onClick={() => setTela('comparacao')}
            >
              Comparação
            </button>
            <button className={tela === 'ganhar' ? 'ativo' : ''} onClick={() => setTela('ganhar')}>
              Onde ganhar tempo
            </button>
          </div>
          <button
            className="btn-perigo"
            onClick={() => {
              setAnalise(null)
              setTela('upload')
              setSelecionados([])
            }}
          >
            Novo treino
          </button>
        </div>
      </div>

      {/* Avisos de leitura (dados que não puderam ser lidos com confiança). */}
      {analise.avisos_parsing.length > 0 && (
        <div className="aviso-box">
          <button
            onClick={() => setMostrarAvisos((v) => !v)}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'inherit',
              padding: 0,
              font: 'inherit',
              textAlign: 'left',
            }}
          >
            {analise.avisos_parsing.length} aviso(s) de leitura — dados ausentes aparecem como
            “sem leitura”, nunca preenchidos. {mostrarAvisos ? 'Ocultar' : 'Ver quais'}
          </button>
          {mostrarAvisos && (
            <ul
              style={{
                margin: '0.6rem 0 0',
                paddingLeft: '1.2rem',
                maxHeight: 180,
                overflowY: 'auto',
                fontSize: '0.82rem',
              }}
            >
              {analise.avisos_parsing.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {tela === 'comparacao' && (
        <ComparacaoScreen
          analise={analise}
          selecionados={selecionadosOrdenados}
          aoAlternar={alternarSelecionado}
          aoVerGanharTempo={() => setTela('ganhar')}
        />
      )}
      {tela === 'ganhar' && <GanharTempoScreen analise={analise} selecionados={selecionadosOrdenados} />}
    </div>
  )
}

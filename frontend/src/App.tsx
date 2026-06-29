import { useState } from 'react'
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

  // Sem análise ainda: só a tela de upload.
  if (!analise) {
    return (
      <div className="app">
        <UploadScreen aoConcluir={aoConcluirUpload} />
      </div>
    )
  }

  return (
    <div className="app">
      <div className="topbar">
        <div>
          <div className="titulo">Análise de Voltas</div>
          <div className="arquivo">
            {analise.arquivo_origem} · {analise.num_pilotos} pilotos
          </div>
        </div>
        <div className="nav">
          <button
            className={tela === 'comparacao' ? 'ativo' : ''}
            onClick={() => setTela('comparacao')}
          >
            Comparação
          </button>
          <button className={tela === 'ganhar' ? 'ativo' : ''} onClick={() => setTela('ganhar')}>
            Onde ganhar tempo
          </button>
          <button
            onClick={() => {
              setAnalise(null)
              setTela('upload')
              setSelecionados([])
            }}
          >
            Novo PDF
          </button>
        </div>
      </div>

      {/* Avisos de parsing (dados que não puderam ser lidos com confiança). */}
      {analise.avisos_parsing.length > 0 && (
        <div className="aviso-box">
          {analise.avisos_parsing.length} aviso(s) de leitura do PDF — alguns dados podem estar
          ausentes (mostrados como “sem leitura”, nunca preenchidos).
        </div>
      )}

      {tela === 'comparacao' && (
        <ComparacaoScreen
          analise={analise}
          selecionados={selecionados}
          aoAlternar={alternarSelecionado}
        />
      )}
      {tela === 'ganhar' && <GanharTempoScreen analise={analise} selecionados={selecionados} />}
    </div>
  )
}

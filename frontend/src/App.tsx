import { useMemo, useState } from 'react'
import './App.css'
import { analisarPdfs } from './api'
import { SEM_FILTRO, type Filtros } from './filtros'
import { compararPilotos } from './ordem'
import { ComparacaoScreen } from './screens/ComparacaoScreen'
import { GanharTempoScreen } from './screens/GanharTempoScreen'
import { UploadScreen } from './screens/UploadScreen'
import type { AnaliseSessao, Modo } from './types'

type Tela = 'upload' | 'comparacao' | 'ganhar'

const MODOS: { valor: Modo; nome: string; dica: string }[] = [
  { valor: 'treino', nome: 'Treino', dica: 'Ritmo por saída do box; volta 1 é saída do box.' },
  { valor: 'qualy', nome: 'Qualy', dica: 'Foco em melhor volta, volta teórica e setores.' },
  {
    valor: 'corrida',
    nome: 'Corrida',
    dica: 'Volta 1 é largada; detecta Safety Car pelo grid e mostra o ritmo entre SCs.',
  },
]

export default function App() {
  const [analise, setAnalise] = useState<AnaliseSessao | null>(null)
  const [tela, setTela] = useState<Tela>('upload')
  const [selecionados, setSelecionados] = useState<string[]>([])
  const [mostrarAvisos, setMostrarAvisos] = useState(false)
  // Os PDFs da sessão ficam guardados: trocar o modo reenvia os mesmos
  // arquivos com outras regras, sem pedir o upload de novo.
  const [arquivos, setArquivos] = useState<File[] | null>(null)
  const [recalculando, setRecalculando] = useState(false)
  // Filtros de grupo e classe: ficam aqui (e não em cada tela) para valerem
  // nas duas — a classe escolhida na Comparação vale no "Onde ganhar tempo".
  const [filtros, setFiltros] = useState<Filtros>(SEM_FILTRO)
  const [erroModo, setErroModo] = useState<string | null>(null)

  async function trocarModo(modo: Modo) {
    if (!arquivos || !analise || modo === analise.modo) return
    setRecalculando(true)
    setErroModo(null)
    try {
      setAnalise(await analisarPdfs(arquivos, modo))
    } catch (e) {
      setErroModo(e instanceof Error ? e.message : 'Erro ao recalcular a análise.')
    } finally {
      setRecalculando(false)
    }
  }

  function aoConcluirUpload(a: AnaliseSessao, enviados: File[]) {
    setArquivos(enviados)
    setFiltros(SEM_FILTRO)
    setErroModo(null)
    setAnalise(a)
    // Pré-seleciona os 2 primeiros (melhor volta; na corrida, o resultado).
    const doisPrimeiros = [...a.pilotos]
      .filter((p) => p.melhor_volta_s !== null)
      .sort(compararPilotos(a.modo))
      .slice(0, 2)
      .map((p) => p.numero_carro)
    setSelecionados(doisPrimeiros)
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
  // sempre na posição que fizeram na sessão (melhor volta; na corrida, o
  // resultado oficial). Isso também estabiliza as cores: o primeiro é sempre
  // a 1ª cor — legenda, tabelas e gaps ficam na mesma ordem do resultado.
  const selecionadosOrdenados = useMemo(() => {
    if (!analise) return selecionados
    const porCarro = new Map(analise.pilotos.map((p) => [p.numero_carro, p]))
    const comparar = compararPilotos(analise.modo)
    return [...selecionados].sort((a, b) => {
      const pa = porCarro.get(a)
      const pb = porCarro.get(b)
      return pa && pb ? comparar(pa, pb) : 0
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
        {/* Modo: as regras da análise. Vem do PDF ("Practice/Qualifying/Race"),
            mas o engenheiro pode trocar — ex.: um warm-up que vale como treino. */}
        <div className="seletor-modo" role="group" aria-label="Analisar a sessão como">
          <span className="rotulo">Analisar como</span>
          {MODOS.map(({ valor, nome, dica }) => (
            <button
              key={valor}
              className={analise.modo === valor ? 'ativo' : ''}
              aria-pressed={analise.modo === valor}
              title={dica}
              disabled={recalculando}
              onClick={() => trocarModo(valor)}
            >
              {nome}
              {analise.modo_detectado === valor && <small>PDF</small>}
            </button>
          ))}
          {recalculando && <span className="recalculando">recalculando…</span>}
        </div>
        <div className="arquivo num">
          {analise.grupos.length > 1
            ? `${analise.grupos.length} grupos juntados (${analise.grupos
                .map((g) => `${g.sigla}: ${g.num_pilotos}`)
                .join(' · ')})`
            : analise.arquivo_origem}{' '}
          · {analise.num_pilotos} pilotos
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
              setArquivos(null)
              setTela('upload')
              setSelecionados([])
            }}
          >
            Nova sessão
          </button>
        </div>
      </div>

      {erroModo && (
        <div className="erro-box" style={{ marginTop: 0 }}>
          <b>Não foi possível trocar o modo.</b>
          <div style={{ marginTop: '0.35rem' }}>{erroModo}</div>
        </div>
      )}

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
          filtros={filtros}
          aoMudarFiltros={setFiltros}
        />
      )}
      {tela === 'ganhar' && (
        <GanharTempoScreen
          analise={analise}
          selecionados={selecionadosOrdenados}
          filtros={filtros}
          aoMudarFiltros={setFiltros}
        />
      )}
    </div>
  )
}

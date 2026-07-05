import { useRef, useState } from 'react'
import { analisarPdf } from '../api'
import type { AnaliseSessao } from '../types'

interface Props {
  aoConcluir: (analise: AnaliseSessao) => void
}

/**
 * Tela 1 — Entrada dos relatórios da sessão.
 * O Laptimes é obrigatório (é dele que saem as voltas). O resumo
 * QualifyReduced é opcional e acrescenta as classes (ELITE/MASTER).
 */
export function UploadScreen({ aoConcluir }: Props) {
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [arrastando, setArrastando] = useState(false)
  const [resumo, setResumo] = useState<File | null>(null)
  const inputPrincipal = useRef<HTMLInputElement>(null)
  const inputResumo = useRef<HTMLInputElement>(null)

  async function processar(arquivo: File) {
    setErro(null)
    setCarregando(true)
    try {
      const analise = await analisarPdf(arquivo, resumo)
      aoConcluir(analise)
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'Erro desconhecido ao analisar o PDF.')
    } finally {
      setCarregando(false)
    }
  }

  if (carregando) {
    return (
      <div>
        <div className="spinner" />
        <p className="status">Lendo os relatórios e calculando as métricas…</p>
      </div>
    )
  }

  return (
    <div className="upload-wrap">
      <h1 className="upload-titulo">Análise de voltas</h1>
      <p className="upload-sub">
        Do relatório de cronometragem ao ponto da pista onde dá para ganhar tempo.
      </p>

      <div
        className={`upload-area${arrastando ? ' arrastando' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setArrastando(true)
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={(e) => {
          e.preventDefault()
          setArrastando(false)
          const arquivo = e.dataTransfer.files?.[0]
          if (arquivo) processar(arquivo)
        }}
      >
        <div className="rotulo">Relatório Laptimes — obrigatório</div>
        <p style={{ margin: '0 0 0.9rem' }}>
          Solte aqui o PDF de voltas do treino (Orbits / MyLaps), ou
        </p>
        <button onClick={() => inputPrincipal.current?.click()}>Escolher o PDF de voltas</button>
        <input
          ref={inputPrincipal}
          type="file"
          accept="application/pdf"
          style={{ display: 'none' }}
          onChange={(e) => {
            const arquivo = e.target.files?.[0]
            // Limpa o valor do input: o navegador só dispara onChange quando o
            // valor MUDA, então sem isso escolher o MESMO arquivo de novo (ex.
            // depois de um erro) não faria nada.
            e.target.value = ''
            if (arquivo) processar(arquivo)
          }}
        />
      </div>

      <div className="upload-resumo">
        <span>
          Resumo QualifyReduced — opcional, acrescenta as classes e a posição oficial.
        </span>
        {resumo ? (
          <span className="ok num">{resumo.name}</span>
        ) : (
          <button onClick={() => inputResumo.current?.click()}>Adicionar resumo</button>
        )}
        {resumo && <button onClick={() => setResumo(null)}>Remover</button>}
        <input
          ref={inputResumo}
          type="file"
          accept="application/pdf"
          style={{ display: 'none' }}
          onChange={(e) => {
            const arquivo = e.target.files?.[0] ?? null
            // Mesmo motivo do input principal: sem limpar o valor, remover o
            // resumo e escolher o MESMO arquivo de novo não dispara onChange.
            e.target.value = ''
            setResumo(arquivo)
          }}
        />
      </div>

      {erro && (
        <div className="erro-box">
          <b>O arquivo não pôde ser usado.</b>
          <div style={{ marginTop: '0.35rem' }}>{erro}</div>
        </div>
      )}
    </div>
  )
}

import { useRef, useState } from 'react'
import { analisarPdf } from '../api'
import type { AnaliseSessao } from '../types'

interface Props {
  aoConcluir: (analise: AnaliseSessao) => void
}

/**
 * Tela 1 — Upload do PDF de treino.
 * Única ação possível: escolher/arrastar o PDF. Estados: carregando, erro
 * (PDF não reconhecido) e aviso parcial (parsing trouxe avisos).
 */
export function UploadScreen({ aoConcluir }: Props) {
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [arrastando, setArrastando] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function processar(arquivo: File) {
    setErro(null)
    setCarregando(true)
    try {
      const analise = await analisarPdf(arquivo)
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
        <p className="status">Lendo o PDF e calculando as métricas…</p>
      </div>
    )
  }

  return (
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
      <h1>Análise de Voltas</h1>
      <p>Arraste o PDF do treino aqui ou</p>
      <button onClick={() => inputRef.current?.click()}>Selecionar PDF do treino</button>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        style={{ display: 'none' }}
        onChange={(e) => {
          const arquivo = e.target.files?.[0]
          if (arquivo) processar(arquivo)
        }}
      />
      <p className="dica">Use o relatório "Laptimes" exportado do cronômetro (Orbits / MyLaps).</p>

      {erro && (
        <div className="erro-box">
          <strong>Não foi possível ler este PDF.</strong>
          <div style={{ marginTop: '0.4rem' }}>{erro}</div>
        </div>
      )}
    </div>
  )
}

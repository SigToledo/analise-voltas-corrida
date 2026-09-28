import { useRef, useState } from 'react'
import { analisarPdfs } from '../api'
import type { AnaliseSessao } from '../types'

interface Props {
  /** Devolve também os arquivos: trocar o modo depois reenvia os mesmos PDFs. */
  aoConcluir: (analise: AnaliseSessao, arquivos: File[]) => void
}

/** Mesmo arquivo escolhido duas vezes (nome + tamanho): entra uma vez só. */
function chave(f: File): string {
  return `${f.name}|${f.size}`
}

/**
 * Tela 1 — Entrada dos relatórios da sessão.
 * Tudo numa área só, em qualquer ordem: o Laptimes (obrigatório — é dele que
 * saem as voltas; um por grupo quando a sessão roda em grupos, como os
 * treinos da MBR) e os resumos QualifyReduced/RaceFull (opcionais: classe e
 * posição). O backend identifica cada PDF pelo conteúdo.
 */
export function UploadScreen({ aoConcluir }: Props) {
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [arrastando, setArrastando] = useState(false)
  const [arquivos, setArquivos] = useState<File[]>([])
  const input = useRef<HTMLInputElement>(null)

  function adicionar(novos: FileList | null) {
    if (!novos) return
    setErro(null)
    setArquivos((atuais) => {
      const vistos = new Set(atuais.map(chave))
      return [...atuais, ...[...novos].filter((f) => !vistos.has(chave(f)))]
    })
  }

  async function analisar() {
    setErro(null)
    setCarregando(true)
    try {
      aoConcluir(await analisarPdfs(arquivos), arquivos)
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'Erro desconhecido ao analisar os PDFs.')
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
          adicionar(e.dataTransfer.files)
        }}
      >
        <div className="rotulo">PDFs da sessão</div>
        <p style={{ margin: '0 0 0.4rem' }}>
          Solte aqui o <b>Laptimes</b> (Orbits / MyLaps) e, se tiver, o resumo{' '}
          <b>QualifyReduced</b> ou <b>RaceFull</b>, que traz classe e posição.
        </p>
        <p className="upload-dica">
          Sessão em grupos (ex.: treino da MBR em Grupo 1 e Grupo 2)? Mande os PDFs de todos os
          grupos juntos: a análise fica numa tela só.
        </p>
        <button onClick={() => input.current?.click()}>Escolher PDFs</button>
        <input
          ref={input}
          type="file"
          accept="application/pdf"
          multiple
          style={{ display: 'none' }}
          onChange={(e) => {
            adicionar(e.target.files)
            // Limpa o valor: o navegador só dispara onChange quando o valor
            // MUDA, então sem isso escolher o MESMO arquivo de novo (ex.
            // depois de removê-lo) não faria nada.
            e.target.value = ''
          }}
        />
      </div>

      {arquivos.length > 0 && (
        <div className="upload-lista">
          <ul>
            {arquivos.map((f) => (
              <li key={chave(f)}>
                <span className="num">{f.name}</span>
                <button
                  className="remover"
                  aria-label={`Remover ${f.name}`}
                  onClick={() => setArquivos((atuais) => atuais.filter((x) => x !== f))}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
          <button className="cta-ganhar" onClick={analisar}>
            Analisar {arquivos.length === 1 ? '1 arquivo' : `${arquivos.length} arquivos`} →
          </button>
        </div>
      )}

      {erro && (
        <div className="erro-box">
          <b>Os arquivos não puderam ser usados.</b>
          <div style={{ marginTop: '0.35rem' }}>{erro}</div>
        </div>
      )}
    </div>
  )
}

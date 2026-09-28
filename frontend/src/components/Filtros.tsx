import { classesDaSessao, type Filtros } from '../filtros'
import { horaDoGrupo } from '../grupos'
import type { AnaliseSessao } from '../types'

interface Props {
  analise: AnaliseSessao
  filtros: Filtros
  aoMudar: (filtros: Filtros) => void
  /** false: só a classe (no "Onde ganhar tempo" o grupo não muda nada). */
  mostrarGrupo?: boolean
}

/**
 * Barras de filtro da sessão: GRUPO (só com grupos juntados) e CLASSE (só
 * quando o resumo oficial trouxe a classe dos pilotos). Os filtros ficam no
 * App, então valem nas duas telas — Comparação e Onde ganhar tempo.
 */
export function BarraFiltros({ analise, filtros, aoMudar, mostrarGrupo = true }: Props) {
  const classes = classesDaSessao(analise.pilotos)
  const temGrupos = mostrarGrupo && analise.grupos.length > 1

  return (
    <>
      {temGrupos && (
        <div className="filtro-grupo" role="group" aria-label="Filtrar pilotos por grupo">
          <span className="rotulo">Grupo</span>
          <button
            className={filtros.grupo === null ? 'ativo' : ''}
            aria-pressed={filtros.grupo === null}
            onClick={() => aoMudar({ ...filtros, grupo: null })}
          >
            Todos <small>{analise.num_pilotos}</small>
          </button>
          {analise.grupos.map((g) => (
            <button
              key={g.sigla}
              className={filtros.grupo === g.sigla ? 'ativo' : ''}
              aria-pressed={filtros.grupo === g.sigla}
              title={g.sessao ?? g.rotulo}
              onClick={() => aoMudar({ ...filtros, grupo: g.sigla })}
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

      {classes.length > 0 ? (
        <div className="filtro-grupo" role="group" aria-label="Filtrar pilotos por classe">
          <span className="rotulo">Classe</span>
          <button
            className={filtros.classe === null ? 'ativo' : ''}
            aria-pressed={filtros.classe === null}
            onClick={() => aoMudar({ ...filtros, classe: null })}
          >
            Todas
          </button>
          {classes.map(({ classe, num_pilotos }) => (
            <button
              key={classe}
              className={filtros.classe === classe ? 'ativo' : ''}
              aria-pressed={filtros.classe === classe}
              onClick={() => aoMudar({ ...filtros, classe })}
            >
              {classe}
              <small>{num_pilotos}</small>
            </button>
          ))}
        </div>
      ) : (
        <p className="dica-filtro">
          Para filtrar por classe, envie também o resumo oficial (QualifyReduced ou RaceFull): a
          classe de cada piloto vem dele.
        </p>
      )}
    </>
  )
}

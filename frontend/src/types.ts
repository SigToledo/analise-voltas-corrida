// Tipos que espelham a resposta do backend (AnaliseSessao em
// backend/app/models/metrics.py). Manter em sincronia com o backend.
//
// Importante: campos que o PDF pode não trazer são `number | null`. `null`
// significa "não foi lido" — nunca tratar como 0 nem inventar no gráfico.

/** Regras de análise: definem o que é largada, Safety Car e trecho. */
export type Modo = 'treino' | 'qualy' | 'corrida'

/**
 * Tipo da volta (calculado pelo backend, não vem do PDF). Só 'normal' entra
 * no ritmo; as outras têm um motivo claro para o tempo não representá-lo.
 */
export type TipoVolta =
  | 'normal'
  | 'largada'
  | 'saida_box'
  | 'entrada_box'
  | 'safety_car'
  | 'relargada'

export interface VoltaLeitura {
  numero_volta: number
  eh_volta_pit: boolean
  /** Volta 1 ou volta seguinte a uma de pit: o tempo parado no box não é
   *  contado pelo cronômetro, então o total é irreal e fica fora de tudo. */
  eh_volta_saida_box: boolean
  tempo_volta_s: number | null
  /** Destacada em negrito no PDF: a melhor volta OFICIAL do piloto. */
  melhor_oficial: boolean
  /** Um tempo por setor (S1, S2…); a quantidade vem do cabeçalho do PDF. */
  setores_s: (number | null)[]
  velocidade_radar_kmh: number | null
  campos_ausentes: string[]
  tipo: TipoVolta
  /** Nº do provável Safety Car em que a volta caiu (inferido pelo grid). */
  neutralizacao: number | null
  /** Trecho: entre SCs (corrida) ou saída do box (treino/qualy). */
  trecho: number | null
}

export interface MetadadosSessao {
  evento: string | null
  pista: string | null
  sessao: string | null
  data_hora: string | null
  duracao: string | null
  etapa: string | null
  tipo_sessao: Modo | null
}

export interface RitmoTrecho {
  trecho: number
  /** Voltas de ritmo do trecho que entraram na mediana. */
  voltas: number[]
  mediana_s: number | null
  /** Menos de 4 voltas: vale como indício. */
  poucas_voltas: boolean
}

/** Provável Safety Car: a maioria do grid lenta ao mesmo tempo. */
export interface PeriodoNeutralizacao {
  numero: number
  /** Segundos de prova, aproximados (soma das voltas). */
  inicio_s: number
  fim_s: number
  volta_inicial_lider: number | null
  volta_final_lider: number | null
}

export interface MetricasPiloto {
  numero_carro: string
  nome: string
  classe: string | null
  /** Posição no resumo oficial; com grupos juntados, DENTRO do grupo. */
  posicao_oficial: number | null
  /** Grupo da sessão ('G1', 'G2', 'SUPER'…) quando vários grupos foram juntados. */
  grupo: string | null
  melhor_volta_s: number | null
  /** 'oficial' = destacada no PDF; 'calculada' = relatório sem destaque. */
  origem_melhor_volta: 'oficial' | 'calculada' | null
  /** Voltas mais rápidas que a oficial: canceladas pela cronometragem. */
  voltas_desconsideradas: number[]
  melhor_volta_teorica_s: number | null
  gap_real_para_teorica_s: number | null
  /** Mediana das voltas de ritmo (tipo 'normal'). */
  mediana_voltas_limpas_s: number | null
  /** Dispersão robusta (MAD × 1,4826), em segundos. */
  consistencia_s: number | null
  num_voltas_limpas: number
  /** Menos de 4 voltas de ritmo: mediana e consistência valem como indício. */
  poucas_voltas: boolean
  ritmo_por_trecho: RitmoTrecho[]
  numero_volta_melhor: number | null
  melhores_setores_s: (number | null)[]
  radar_maximo_kmh: number | null
  radar_mediano_kmh: number | null
  voltas_outlier: number[]
  avisos: string[]
}

export interface DonoDoSetor {
  setor: number
  tempo_s: number | null
  numero_carro_dono: string | null
  nome_dono: string | null
  grupo_dono: string | null
}

/** Um dos grupos juntados na análise (ex.: MBR treina em Grupo 1 e Grupo 2). */
export interface GrupoSessao {
  sigla: string
  rotulo: string
  sessao: string | null
  data_hora: string | null
  arquivo: string
  num_pilotos: number
}

export interface VoltaIdealEquipe {
  setores: DonoDoSetor[]
  total_s: number | null
  avisos: string[]
}

export interface GapSetorPiloto {
  numero_carro: string
  nome: string
  tempo_setor_s: number | null
  gap_para_referencia_s: number | null
  gap_para_referencia_pct: number | null
}

export interface ComparacaoSetor {
  setor: number
  referencia_numero_carro: string | null
  referencia_tempo_s: number | null
  pilotos: GapSetorPiloto[]
  avisos: string[]
}

export interface AnaliseSessao {
  arquivo_origem: string
  num_pilotos: number
  num_setores: number
  tem_radar: boolean
  modo: Modo
  /** Tipo de sessão lido do PDF (o usuário pode escolher outro modo). */
  modo_detectado: Modo | null
  neutralizacoes: PeriodoNeutralizacao[]
  metadados: MetadadosSessao | null
  pilotos: MetricasPiloto[]
  volta_ideal_equipe: VoltaIdealEquipe
  comparacao_setores: ComparacaoSetor[]
  voltas_por_carro: Record<string, VoltaLeitura[]>
  /** Grupos juntados, na ordem do horário. Vazio numa sessão única. */
  grupos: GrupoSessao[]
  avisos_parsing: string[]
}

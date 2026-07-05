// Tipos que espelham a resposta do backend (AnaliseSessao em
// backend/app/models/metrics.py). Manter em sincronia com o backend.
//
// Importante: campos que o PDF pode não trazer são `number | null`. `null`
// significa "não foi lido" — nunca tratar como 0 nem inventar no gráfico.

export interface VoltaLeitura {
  numero_volta: number
  eh_volta_pit: boolean
  /** Volta 1 ou volta seguinte a uma de pit: o tempo parado no box não é
   *  contado pelo cronômetro, então o total é irreal e fica fora de tudo. */
  eh_volta_saida_box: boolean
  tempo_volta_s: number | null
  setor1_s: number | null
  setor2_s: number | null
  setor3_s: number | null
  velocidade_radar_kmh: number | null
  campos_ausentes: string[]
}

export interface MetadadosSessao {
  evento: string | null
  pista: string | null
  sessao: string | null
  data_hora: string | null
  duracao: string | null
}

export interface MetricasPiloto {
  numero_carro: string
  nome: string
  classe: string | null
  posicao_oficial: number | null
  melhor_volta_s: number | null
  melhor_volta_teorica_s: number | null
  gap_real_para_teorica_s: number | null
  mediana_voltas_limpas_s: number | null
  consistencia_desvio_padrao_s: number | null
  num_voltas_limpas: number
  numero_volta_melhor: number | null
  melhor_setor1_s: number | null
  melhor_setor2_s: number | null
  melhor_setor3_s: number | null
  melhor_sstrap_kmh: number | null
  sstrap_medio_kmh: number | null
  voltas_outlier: number[]
  avisos: string[]
}

export interface DonoDoSetor {
  setor: number
  tempo_s: number | null
  numero_carro_dono: string | null
  nome_dono: string | null
}

export interface VoltaIdealEquipe {
  setor1: DonoDoSetor
  setor2: DonoDoSetor
  setor3: DonoDoSetor
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
  metadados: MetadadosSessao | null
  pilotos: MetricasPiloto[]
  volta_ideal_equipe: VoltaIdealEquipe
  comparacao_setores: ComparacaoSetor[]
  voltas_por_carro: Record<string, VoltaLeitura[]>
  avisos_parsing: string[]
}

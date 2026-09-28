"""
Modelos (Pydantic) para os RESULTADOS dos cálculos de métricas.

Separados dos modelos de extração (lap_data.py) de propósito: lap_data
descreve "o que foi lido do PDF"; este arquivo descreve "o que calculamos a
partir disso". Manter separado deixa claro o que é dado bruto e o que é
derivado.

Regra de sempre: quando um número não pode ser calculado com confiança (ex:
um setor sem nenhuma leitura válida), o campo fica None e a explicação vai
para a lista `avisos` — nunca um valor inventado.
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.models.lap_data import VoltaLeitura


class RitmoTrecho(BaseModel):
    """Ritmo de um piloto num trecho da sessão (entre Safety Cars ou numa saída do box)."""

    trecho: int = Field(..., description="Número do trecho (ver VoltaLeitura.trecho).")
    voltas: list[int] = Field(
        default_factory=list, description="Voltas de ritmo do trecho que entraram na mediana."
    )
    mediana_s: Optional[float] = Field(None, description="Mediana dessas voltas.")
    poucas_voltas: bool = Field(
        False, description="Menos de 4 voltas: a mediana vale como indício, não como ritmo firme."
    )


class MetricasPiloto(BaseModel):
    """Métricas individuais de um piloto na sessão."""

    numero_carro: str
    nome: str
    classe: Optional[str] = Field(
        None,
        description=(
            "Classe/categoria (ex: ELITE, MASTER). Vem do relatório de resumo "
            "(QualifyReduced), quando enviado — o Laptimes não traz classe."
        ),
    )
    posicao_oficial: Optional[int] = Field(
        None,
        description=(
            "Posição no resumo oficial, quando enviado. Com grupos juntados, é a "
            "posição DENTRO do grupo (cada grupo tem o seu resumo)."
        ),
    )
    grupo: Optional[str] = Field(
        None, description="Grupo da sessão (ex.: 'G1'), quando vários grupos foram juntados."
    )

    melhor_volta_s: Optional[float] = Field(
        None, description="Melhor volta do piloto (ver origem_melhor_volta). None se não houver."
    )
    origem_melhor_volta: Optional[str] = Field(
        None,
        description=(
            "'oficial' = a volta que o próprio PDF destaca em negrito (já descontadas "
            "voltas canceladas pela direção de prova); 'calculada' = relatório sem "
            "destaque, então aplicamos a regra da volta completa mais rápida."
        ),
    )
    voltas_desconsideradas: list[int] = Field(
        default_factory=list,
        description=(
            "Voltas completas MAIS RÁPIDAS que a melhor oficial: a cronometragem as "
            "desconsiderou (provável cancelamento, ex.: limite de pista). Ficam fora do "
            "ritmo e dos melhores setores."
        ),
    )
    melhor_volta_teorica_s: Optional[float] = Field(
        None,
        description=(
            "Soma dos melhores setores do piloto. None se algum setor não tiver "
            "nenhuma leitura válida."
        ),
    )
    gap_real_para_teorica_s: Optional[float] = Field(
        None,
        description=(
            "melhor_volta_s - melhor_volta_teorica_s (tempo que o piloto 'deixou "
            "na mesa'). None se faltar uma das duas."
        ),
    )

    mediana_voltas_limpas_s: Optional[float] = Field(
        None,
        description=(
            "Mediana das voltas de RITMO (tipo 'normal', completas, não desconsideradas). "
            "A mediana é o tempo 'do meio': uma volta com tráfego não a puxa, como puxaria a média."
        ),
    )
    consistencia_s: Optional[float] = Field(
        None,
        description=(
            "Dispersão típica das voltas de ritmo, em segundos (MAD × 1,4826 — a versão "
            "robusta do desvio padrão: ignora uma ou outra volta atípica). Quanto menor, "
            "mais constante. None com menos de 2 voltas de ritmo."
        ),
    )
    num_voltas_limpas: int = Field(0, description="Quantas voltas de ritmo entraram nas estatísticas.")
    poucas_voltas: bool = Field(
        False,
        description="Menos de 4 voltas de ritmo: mediana e consistência valem como indício.",
    )
    ritmo_por_trecho: list[RitmoTrecho] = Field(
        default_factory=list,
        description="Mediana por trecho: entre Safety Cars (corrida) ou por saída do box (treino/qualy).",
    )

    numero_volta_melhor: Optional[int] = Field(
        None, description="Número da volta em que o piloto fez a melhor volta (coluna NA do oficial)."
    )

    melhores_setores_s: list[Optional[float]] = Field(
        default_factory=list,
        description="Melhor tempo de cada setor (S1, S2…), na ordem. None = sem leitura válida.",
    )

    radar_maximo_kmh: Optional[float] = Field(
        None, description="Maior velocidade de radar (km/h) fora do box. Indício de velocidade de ponta."
    )
    radar_mediano_kmh: Optional[float] = Field(
        None, description="Mediana do radar (km/h) nas voltas de ritmo com leitura."
    )

    voltas_outlier: list[int] = Field(
        default_factory=list,
        description=(
            "Voltas de ritmo anormalmente lentas (> mediana + 3 × consistência): provável "
            "tráfego ou bandeira amarela local. Sinalizadas, NÃO removidas — a mediana quase "
            "não sofre com elas. Só com 4 ou mais voltas de ritmo."
        ),
    )

    avisos: list[str] = Field(default_factory=list)


class PeriodoNeutralizacao(BaseModel):
    """
    Um provável Safety Car: trecho da corrida em que a MAIORIA do grid ficou
    lenta ao mesmo tempo. É uma inferência (o PDF não marca SC), por isso vem
    com as voltas e o horário aproximado para o engenheiro conferir.
    """

    numero: int
    inicio_s: float = Field(
        ...,
        description=(
            "Início aproximado, em segundos de prova (soma das voltas; não inclui os "
            "poucos segundos até cada carro cruzar a linha na largada)."
        ),
    )
    fim_s: float
    volta_inicial_lider: Optional[int] = Field(
        None, description="Primeira volta do líder afetada (os retardatários têm outra numeração)."
    )
    volta_final_lider: Optional[int] = None


class DonoDoSetor(BaseModel):
    """O melhor tempo de um setor e de quem é."""

    setor: int
    tempo_s: Optional[float] = None
    numero_carro_dono: Optional[str] = None
    nome_dono: Optional[str] = None
    grupo_dono: Optional[str] = Field(None, description="Grupo do dono, com grupos juntados.")


class GrupoSessao(BaseModel):
    """
    Um dos grupos juntados na análise (ex.: MBR treina em Grupo 1 e Grupo 2).
    Os grupos andam em horários diferentes: a pista pode mudar entre eles.
    """

    sigla: str = Field(..., description="Etiqueta curta: 'G1', 'G2' ou o nome do grupo ('SUPER').")
    rotulo: str = Field(..., description="Nome do grupo como está no PDF: 'GRUPO 1', 'ELITE/MASTER'.")
    sessao: Optional[str] = Field(None, description="Nome completo da sessão desse grupo.")
    data_hora: Optional[str] = Field(None, description="Início da sessão desse grupo.")
    arquivo: str = Field(..., description="Laptimes de onde vieram os pilotos do grupo.")
    num_pilotos: int = 0


class VoltaIdealEquipe(BaseModel):
    """
    A 'volta ideal' combinando os melhores setores de TODOS os pilotos.
    É uma meta teórica: ninguém fez essa volta, mas mostra o potencial do grid.
    """

    setores: list[DonoDoSetor] = Field(
        default_factory=list, description="O dono de cada setor (S1, S2…), na ordem."
    )
    total_s: Optional[float] = Field(
        None, description="Soma dos melhores setores. None se algum setor não tiver leitura."
    )
    avisos: list[str] = Field(default_factory=list)


class GapSetorPiloto(BaseModel):
    """O tempo de um piloto em um setor e o gap dele para a referência (o mais rápido)."""

    numero_carro: str
    nome: str
    tempo_setor_s: Optional[float] = None
    gap_para_referencia_s: Optional[float] = Field(
        None, description="tempo deste piloto - tempo da referência. 0 para o próprio mais rápido."
    )
    gap_para_referencia_pct: Optional[float] = Field(
        None, description="gap em % do tempo da referência. None se não calculável."
    )


class ComparacaoSetor(BaseModel):
    """Comparação de um setor entre os pilotos selecionados."""

    setor: int
    referencia_numero_carro: Optional[str] = Field(
        None, description="Número do carro do piloto mais rápido neste setor (a referência)."
    )
    referencia_tempo_s: Optional[float] = None
    pilotos: list[GapSetorPiloto] = Field(default_factory=list)
    avisos: list[str] = Field(default_factory=list)


class AnaliseSessao(BaseModel):
    """
    Resposta completa da análise de uma sessão: tudo o que o frontend precisa
    para montar as telas de comparação e de 'onde ganhar tempo'.
    """

    arquivo_origem: str
    num_pilotos: int
    num_setores: int = Field(0, description="Quantos setores a pista tem neste relatório.")
    tem_radar: bool = Field(False, description="Se o relatório traz velocidade de radar.")
    modo: str = Field(
        "treino",
        description=(
            "Regras aplicadas: 'treino', 'qualy' ou 'corrida'. Na corrida, a volta 1 é "
            "largada e os Safety Cars são detectados; no treino/qualy, os trechos são as "
            "saídas do box."
        ),
    )
    modo_detectado: Optional[str] = Field(
        None, description="Tipo de sessão lido do PDF (o usuário pode escolher outro modo)."
    )
    neutralizacoes: list[PeriodoNeutralizacao] = Field(
        default_factory=list, description="Prováveis Safety Cars (só no modo corrida)."
    )
    metadados: Optional[dict] = Field(
        None,
        description="Cabeçalho da sessão extraído do PDF: evento, pista, sessão, data/hora, duração.",
    )
    pilotos: list[MetricasPiloto] = Field(default_factory=list)
    volta_ideal_equipe: VoltaIdealEquipe
    voltas_ideais_por_classe: dict[str, VoltaIdealEquipe] = Field(
        default_factory=dict,
        description=(
            "Volta ideal de cada classe (ELITE, MASTER, SUPER…), com a mesma regra da "
            "do grid. Só existe quando a classe veio do resumo oficial."
        ),
    )
    comparacao_setores: list[ComparacaoSetor] = Field(default_factory=list)
    voltas_por_carro: dict[str, list[VoltaLeitura]] = Field(
        default_factory=dict,
        description=(
            "Voltas (dado bruto extraído) de cada piloto, indexadas pelo número do "
            "carro. O frontend usa isso para o gráfico de tempo por volta. Voltas "
            "sem leitura mantêm os campos em null — nunca interpolar no gráfico."
        ),
    )
    grupos: list[GrupoSessao] = Field(
        default_factory=list,
        description=(
            "Grupos juntados nesta análise, na ordem do horário. Vazio numa sessão única."
        ),
    )
    avisos_parsing: list[str] = Field(
        default_factory=list,
        description="Avisos do parser do PDF (dados que não puderam ser lidos com confiança).",
    )

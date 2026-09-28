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
        None, description="Posição no ranking geral do resumo oficial, quando enviado."
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
        None, description="Mediana dos tempos das voltas limpas. None se não houver voltas limpas."
    )
    consistencia_desvio_padrao_s: Optional[float] = Field(
        None,
        description=(
            "Desvio padrão dos tempos das voltas limpas (quanto menor, mais "
            "constante o piloto). None se houver menos de 2 voltas limpas."
        ),
    )
    num_voltas_limpas: int = Field(
        0, description="Quantas voltas limpas (não-pit, com tempo total lido) entraram nas estatísticas."
    )

    numero_volta_melhor: Optional[int] = Field(
        None, description="Número da volta em que o piloto fez a melhor volta (coluna NA do oficial)."
    )

    melhores_setores_s: list[Optional[float]] = Field(
        default_factory=list,
        description="Melhor tempo de cada setor (S1, S2…), na ordem. None = sem leitura válida.",
    )

    melhor_sstrap_kmh: Optional[float] = Field(
        None, description="Maior velocidade de radar (km/h) entre as voltas não-pit. Indício de ponta."
    )
    sstrap_medio_kmh: Optional[float] = Field(
        None, description="Velocidade de radar média (km/h) nas voltas não-pit com leitura."
    )

    voltas_outlier: list[int] = Field(
        default_factory=list,
        description=(
            "Números das voltas válidas anormalmente lentas (> mediana + 1,5x desvio): "
            "provável tráfego/bandeira. Sinalizadas, NÃO removidas — a mediana (robusta) "
            "quase não sofre com elas; servem de alerta ao analisar ritmo."
        ),
    )

    avisos: list[str] = Field(default_factory=list)


class DonoDoSetor(BaseModel):
    """O melhor tempo de um setor e de quem é."""

    setor: int
    tempo_s: Optional[float] = None
    numero_carro_dono: Optional[str] = None
    nome_dono: Optional[str] = None


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
    metadados: Optional[dict] = Field(
        None,
        description="Cabeçalho da sessão extraído do PDF: evento, pista, sessão, data/hora, duração.",
    )
    pilotos: list[MetricasPiloto] = Field(default_factory=list)
    volta_ideal_equipe: VoltaIdealEquipe
    comparacao_setores: list[ComparacaoSetor] = Field(default_factory=list)
    voltas_por_carro: dict[str, list[VoltaLeitura]] = Field(
        default_factory=dict,
        description=(
            "Voltas (dado bruto extraído) de cada piloto, indexadas pelo número do "
            "carro. O frontend usa isso para o gráfico de tempo por volta. Voltas "
            "sem leitura mantêm os campos em null — nunca interpolar no gráfico."
        ),
    )
    avisos_parsing: list[str] = Field(
        default_factory=list,
        description="Avisos do parser do PDF (dados que não puderam ser lidos com confiança).",
    )

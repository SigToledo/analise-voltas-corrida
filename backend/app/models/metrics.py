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


class MetricasPiloto(BaseModel):
    """Métricas individuais de um piloto na sessão."""

    numero_carro: str
    nome: str

    melhor_volta_s: Optional[float] = Field(
        None, description="Menor tempo total entre as voltas não-pit. None se não houver."
    )
    melhor_volta_teorica_s: Optional[float] = Field(
        None,
        description=(
            "Soma do melhor S1 + melhor S2 + melhor S3 do piloto. None se algum "
            "setor não tiver nenhuma leitura válida."
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

    melhor_setor1_s: Optional[float] = None
    melhor_setor2_s: Optional[float] = None
    melhor_setor3_s: Optional[float] = None

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

    setor1: DonoDoSetor
    setor2: DonoDoSetor
    setor3: DonoDoSetor
    total_s: Optional[float] = Field(
        None, description="Soma dos três melhores setores. None se algum setor não tiver leitura."
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

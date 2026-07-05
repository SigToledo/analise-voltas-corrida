"""
Modelos de dados (Pydantic) para o resultado do parsing de um PDF de voltas.

Por que Pydantic e não dict puro?
- O FastAPI já usa Pydantic para validar dados de entrada/saída, então manter
  os mesmos modelos aqui evita duplicar lógica de validação depois.
- Pydantic obriga a gente a ser explícito sobre quais campos são opcionais
  (Optional[...]) — isso ajuda a cumprir a regra de "nunca inventar dado":
  se um campo pode faltar, ele é None, nunca um valor padrão tipo 0.0.
"""

from typing import Optional

from pydantic import BaseModel, Field


class VoltaLeitura(BaseModel):
    """
    Os tempos lidos para UMA volta de UM piloto.

    Todos os campos de tempo são Optional[float] (segundos). Se o PDF não
    trouxe aquele valor de forma legível para essa volta, o campo fica None
    — nunca 0.0 ou qualquer valor "chutado". Quem for consumir esses dados
    (cálculo de métricas, frontend) precisa checar se é None antes de usar.
    """

    numero_volta: int = Field(..., description="Número sequencial da volta (1, 2, 3...).")
    eh_volta_pit: bool = Field(
        ...,
        description="True se o PDF marcou essa volta com o prefixo 'p' (volta de entrada de boxes).",
    )
    eh_volta_saida_box: bool = Field(
        False,
        description=(
            "True se esta é uma volta de SAÍDA de box: a volta 1 da sessão ou a "
            "volta imediatamente seguinte a uma volta 'p'. O cronômetro não conta "
            "parte do tempo parado no box, então o tempo total dessas voltas sai "
            "irrealisticamente baixo (às vezes 'melhor' que a pole) e é "
            "desconsiderado pela cronometragem oficial — e por todas as nossas "
            "análises também."
        ),
    )

    tempo_volta_s: Optional[float] = Field(
        None, description="Tempo total da volta (Lap Tm), em segundos. None se não foi lido."
    )
    setor1_s: Optional[float] = Field(None, description="Tempo do setor 1 (S1 Tm), em segundos.")
    setor2_s: Optional[float] = Field(None, description="Tempo do setor 2 (S2 Tm), em segundos.")
    setor3_s: Optional[float] = Field(None, description="Tempo do setor 3 (S3 Tm), em segundos.")
    velocidade_radar_kmh: Optional[float] = Field(
        None, description="Velocidade de radar (SSTRAP), em km/h."
    )

    campos_ausentes: list[str] = Field(
        default_factory=list,
        description=(
            "Lista com os nomes dos campos que deveriam existir mas não foram "
            "encontrados/lidos com confiança nesta volta (ex: ['setor1_s']). "
            "Vazio significa que todos os campos esperados foram lidos."
        ),
    )


class PilotoLaps(BaseModel):
    """Dados de um piloto extraídos do bloco de voltas do PDF."""

    numero_carro: str = Field(..., description="Número do carro, ex: '171'. Mantido como string.")
    nome: str = Field(..., description="Nome (ou nomes, em caso de dupla) do piloto, ex: 'L.JOSE'.")
    voltas: list[VoltaLeitura] = Field(default_factory=list)

    @property
    def numero_de_voltas(self) -> int:
        """Quantidade de voltas efetivamente extraídas para este piloto."""
        return len(self.voltas)


class ResultadoParsingPDF(BaseModel):
    """
    Resultado completo do parsing de um PDF "Laptimes_sec4".

    avisos: lista de mensagens em texto simples sobre qualquer problema
    encontrado durante o parsing que não impediu o processo, mas que o
    usuário deveria saber (ex: "página 2: texto sobreposto não resolvido
    perto de x=300, top=450"). Isso é o mecanismo de "sinalizar em vez de
    inventar" em nível de documento inteiro.
    """

    arquivo_origem: str
    pilotos: list[PilotoLaps] = Field(default_factory=list)
    avisos: list[str] = Field(default_factory=list)

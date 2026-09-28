"""
Modelos de dados (Pydantic) para o resultado do parsing de um PDF de voltas.

Por que Pydantic e não dict puro?
- O FastAPI já usa Pydantic para validar dados de entrada/saída, então manter
  os mesmos modelos aqui evita duplicar lógica de validação depois.
- Pydantic obriga a gente a ser explícito sobre quais campos são opcionais
  (Optional[...]) — isso ajuda a cumprir a regra de "nunca inventar dado":
  se um campo pode faltar, ele é None, nunca um valor padrão tipo 0.0.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TipoVolta(str, Enum):
    """
    Que tipo de volta é esta — define se ela entra no RITMO do piloto.
    Só a 'normal' (volta lançada, em bandeira verde) entra na mediana e na
    consistência; as demais têm um motivo claro para o tempo não representar
    o ritmo, e ficam visíveis com esse rótulo.
    """

    NORMAL = "normal"            # volta lançada, bandeira verde
    LARGADA = "largada"          # volta 1 de uma corrida (sai parado/lançado atrás do pelotão)
    SAIDA_BOX = "saida_box"      # volta 1 de treino/qualy ou a seguinte a um 'p'
    ENTRADA_BOX = "entrada_box"  # volta marcada com 'p' no PDF
    SAFETY_CAR = "safety_car"    # corrida neutralizada (detectado pelo grid inteiro)
    RELARGADA = "relargada"      # primeira volta depois de um Safety Car


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
    melhor_oficial: bool = Field(
        False,
        description=(
            "True se o PDF imprime o tempo desta volta em NEGRITO: é assim que o "
            "cronômetro marca a melhor volta OFICIAL do piloto (já descontadas "
            "voltas canceladas pela direção de prova, que não têm outra marcação)."
        ),
    )
    setores_s: list[Optional[float]] = Field(
        default_factory=list,
        description=(
            "Tempo de cada setor, em segundos, na ordem S1, S2, S3… A quantidade de "
            "setores vem do cabeçalho do relatório (varia por pista). None = setor "
            "sem leitura nesta volta."
        ),
    )
    velocidade_radar_kmh: Optional[float] = Field(
        None,
        description="Velocidade de radar em km/h (coluna 'SSTRAP' ou 'SPD', conforme o evento).",
    )

    campos_ausentes: list[str] = Field(
        default_factory=list,
        description=(
            "Campos que EXISTEM no relatório mas não foram lidos nesta volta "
            "(ex: ['setor1_s']). Colunas que o relatório nem tem (ex.: pista sem "
            "radar) não entram aqui."
        ),
    )

    # --- Classificação: NÃO vem do PDF, é calculada pela análise ---
    # (app/metrics/tipos_volta.py). Fica aqui porque o frontend precisa dela
    # volta a volta, junto dos tempos.
    tipo: TipoVolta = Field(
        TipoVolta.NORMAL,
        description="Tipo da volta (ver TipoVolta). Só 'normal' entra no ritmo.",
    )
    neutralizacao: Optional[int] = Field(
        None,
        description=(
            "Número do período de Safety Car (1, 2…) em que esta volta caiu. "
            "Inferido pelo grid inteiro ficar lento ao mesmo tempo — não é marcação do PDF."
        ),
    )
    trecho: Optional[int] = Field(
        None,
        description=(
            "Trecho da sessão (1, 2…): na corrida, o intervalo de bandeira verde "
            "entre Safety Cars; no treino/qualy, a saída do box (cada ida à pista). "
            "None nas voltas de Safety Car."
        ),
    )

    @property
    def completa(self) -> bool:
        """Tempo total e TODOS os setores lidos."""
        return self.tempo_volta_s is not None and all(s is not None for s in self.setores_s)


class PilotoLaps(BaseModel):
    """Dados de um piloto extraídos do bloco de voltas do PDF."""

    numero_carro: str = Field(..., description="Número do carro, ex: '171'. Mantido como string.")
    nome: str = Field(..., description="Nome (ou nomes, em caso de dupla) do piloto, ex: 'L.JOSE'.")
    classe: Optional[str] = Field(
        None, description="Classe, quando o próprio Laptimes vem agrupado por classe."
    )
    grupo: Optional[str] = Field(
        None,
        description=(
            "Grupo da sessão (ex.: 'G1', 'G2', 'SUPER') quando vários Laptimes da "
            "mesma sessão foram juntados. None numa sessão única."
        ),
    )
    voltas: list[VoltaLeitura] = Field(default_factory=list)

    @property
    def numero_de_voltas(self) -> int:
        """Quantidade de voltas efetivamente extraídas para este piloto."""
        return len(self.voltas)


class ResultadoParsingPDF(BaseModel):
    """
    Resultado completo do parsing de um PDF "Laptimes".

    avisos: mensagens sobre qualquer problema encontrado durante o parsing que
    não impediu o processo, mas que o usuário deveria saber. É o mecanismo de
    "sinalizar em vez de inventar" em nível de documento inteiro.
    """

    arquivo_origem: str
    num_setores: int = Field(0, description="Quantos setores o relatório tem (do cabeçalho).")
    tem_radar: bool = Field(False, description="Se o relatório tem coluna de velocidade de radar.")
    pilotos: list[PilotoLaps] = Field(default_factory=list)
    avisos: list[str] = Field(default_factory=list)

"""
Parser dos relatórios de RESUMO oficial: QualifyReduced (treino/qualy) e
RaceFull (corrida), nas variantes plana e BY CLASS.

Cada evento configura colunas diferentes, por exemplo:
    Cuiabá:   Pos | No. | Name | Class | Laps | Best Tm | Diff | NA | EQUIPE
    Cascavel: Pos | No. | Name | Class | Best Tm | In Lap | Diff | Gap | Laps | Total Tm | Carro
Por isso cada linha é distribuída pelas colunas DO CABEÇALHO daquela página
(ver cabecalho.distribuir_linha), nunca por posição ou ordem fixa.

Só é tratada como linha de piloto a que tem número de carro inteiro e nome.
Valor que não converte (ex.: "DNF" onde deveria haver tempo) fica None e vira
aviso — nunca "consertado".
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.parser.cabecalho import distribuir_linha
from app.parser.conversao import inteiro, tempo_em_segundos, voltas_atras
from app.parser.pdf_texto import LeitorPDF, agrupar_linhas
from app.parser.tipo_pdf import (
    SECOES_FIM_DA_TABELA,
    SECOES_NAO_CLASSE,
    Identificacao,
    TipoRelatorio,
    localizar_cabecalho,
    titulo_de_secao,
)

_TITULOS_CARRO = ("No.", "No", "Nº")
_TITULOS_VOLTA_DA_MELHOR = ("NA", "In Lap")


class PilotoResumo(BaseModel):
    """Uma linha do resumo oficial. Campo que o relatório não tem fica None."""

    posicao: Optional[int] = Field(
        None, description="Posição (na variante BY CLASS, posição DENTRO da classe)."
    )
    status: Optional[str] = Field(None, description="Texto na coluna de posição (ex.: DNF, NC).")
    numero_carro: str
    nome: Optional[str] = None
    classe: Optional[str] = None
    voltas: Optional[int] = None
    melhor_volta_s: Optional[float] = None
    volta_da_melhor: Optional[int] = Field(
        None, description="Volta em que fez a melhor marca (coluna 'NA' ou 'In Lap')."
    )
    diff_s: Optional[float] = Field(None, description="Diferença para o líder, em segundos.")
    diff_voltas: Optional[int] = Field(None, description="Diferença em voltas ('1 Lap'), em corrida.")
    gap_s: Optional[float] = Field(None, description="Diferença para o carro da frente.")
    tempo_total_s: Optional[float] = None


class ResumoOficial(BaseModel):
    arquivo_origem: str
    tipo: str = Field(..., description="'resumo' (QualifyReduced) ou 'resultado_corrida' (RaceFull).")
    agrupado_por_classe: bool = False
    metadados: Optional[dict] = None
    pilotos: list[PilotoResumo] = Field(default_factory=list)
    avisos: list[str] = Field(default_factory=list)


def _converter(valores: dict[str, str], titulo: str, conversor, ref: str, avisos: list[str]):
    """Converte a célula; se há texto mas ele não converte, avisa e devolve None."""
    texto = valores.get(titulo)
    if texto is None:
        return None
    valor = conversor(texto)
    if valor is None:
        avisos.append(f"{ref}: '{titulo}' ilegível ('{texto}').")
    return valor


def _diferenca(valores: dict[str, str], titulo: str, ref: str, avisos: list[str]):
    """'0.879' → (0.879, None) ; '1 Lap' → (None, 1)."""
    texto = valores.get(titulo)
    if texto is None:
        return None, None
    em_voltas = voltas_atras(texto)
    if em_voltas is not None:
        return None, em_voltas
    segundos = tempo_em_segundos(texto)
    if segundos is None:
        avisos.append(f"{ref}: '{titulo}' ilegível ('{texto}').")
    return segundos, None


def parse_resumo(leitor: LeitorPDF, ident: Identificacao, nome_arquivo: str | None = None) -> ResumoOficial:
    avisos: list[str] = []
    pilotos: list[PilotoResumo] = []
    classe_secao: str | None = None

    for n in range(leitor.num_paginas):
        linhas = agrupar_linhas(leitor.palavras(n))
        achado = localizar_cabecalho(linhas)
        if achado is None:
            continue
        indice, colunas = achado
        for linha in linhas[indice + 1 :]:
            secao = titulo_de_secao(linha, colunas)
            if secao is not None:
                if secao.lower() in SECOES_FIM_DA_TABELA:
                    break  # comunicados: nenhuma linha dali é piloto
                # "Not classified" e afins não são classe: a partir dali a
                # classe fica desconhecida (a coluna Class, se houver, vale).
                classe_secao = None if secao.lower() in SECOES_NAO_CLASSE else secao
                continue

            d = distribuir_linha(linha, colunas)
            carro = next((d.valores[t] for t in _TITULOS_CARRO if t in d.valores), None)
            nome = d.valores.get("Name")
            if carro is None or inteiro(carro) is None or not nome:
                continue  # não é linha de piloto (ex.: estatísticas no pé da tabela)

            ref = f"Resumo, carro {carro}"
            for titulo in d.conflitos:
                avisos.append(f"{ref}: dois valores na coluna '{titulo}' — descartados.")
                d.valores.pop(titulo, None)
            if d.sem_coluna:
                avisos.append(f"{ref}: valores sem coluna {d.sem_coluna} — ignorados.")

            pos_txt = d.valores.get("Pos")
            diff_s, diff_voltas = _diferenca(d.valores, "Diff", ref, avisos)
            gap_s, _ = _diferenca(d.valores, "Gap", ref, avisos)
            titulo_na = next((t for t in _TITULOS_VOLTA_DA_MELHOR if t in d.valores), None)

            pilotos.append(
                PilotoResumo(
                    posicao=inteiro(pos_txt),
                    status=pos_txt if pos_txt is not None and inteiro(pos_txt) is None else None,
                    numero_carro=carro,
                    nome=nome,
                    classe=d.valores.get("Class") or d.valores.get("Classe") or classe_secao,
                    voltas=_converter(d.valores, "Laps", inteiro, ref, avisos),
                    melhor_volta_s=_converter(d.valores, "Best Tm", tempo_em_segundos, ref, avisos),
                    volta_da_melhor=(
                        _converter(d.valores, titulo_na, inteiro, ref, avisos) if titulo_na else None
                    ),
                    diff_s=diff_s,
                    diff_voltas=diff_voltas,
                    gap_s=gap_s,
                    tempo_total_s=_converter(d.valores, "Total Tm", tempo_em_segundos, ref, avisos),
                )
            )

    # O RaceFull imprime a classificação inteira mais de uma vez (ex.: 47 carros
    # em 94 linhas). Vale a primeira ocorrência de cada carro; repetição com
    # valores diferentes vira aviso em vez de sobrescrever em silêncio.
    unicos: dict[str, PilotoResumo] = {}
    for p in pilotos:
        primeiro = unicos.get(p.numero_carro)
        if primeiro is None:
            unicos[p.numero_carro] = p
        elif primeiro.model_dump(exclude={"posicao", "classe"}) != p.model_dump(exclude={"posicao", "classe"}):
            avisos.append(f"Resumo, carro {p.numero_carro}: aparece de novo com valores diferentes — mantida a 1ª linha.")
    pilotos = list(unicos.values())

    if not pilotos:
        avisos.append("Nenhuma linha de piloto reconhecida no resumo.")

    return ResumoOficial(
        arquivo_origem=nome_arquivo or leitor.caminho,
        tipo=ident.tipo.value,
        agrupado_por_classe=ident.agrupado_por_classe,
        metadados=ident.metadados.como_dict(),
        pilotos=pilotos,
        avisos=avisos,
    )


def parse_resumo_pdf(caminho_pdf: str) -> ResumoOficial:
    """Atalho: identifica e lê um resumo (usado em testes e scripts)."""
    from app.parser.tipo_pdf import identificar

    with LeitorPDF(caminho_pdf) as leitor:
        ident = identificar(leitor)
        if ident.tipo not in (TipoRelatorio.RESUMO, TipoRelatorio.RESULTADO_CORRIDA):
            raise ValueError(f"{caminho_pdf}: não é um resumo ({ident.tipo.value}).")
        return parse_resumo(leitor, ident)

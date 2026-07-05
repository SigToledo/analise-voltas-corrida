"""
Parser dos relatórios de resumo "QualifyReduced" (plano e BY CLASS).

Cada linha de piloto tem as colunas:
    Pos | No. | Name | Class | Laps | Best Tm | Diff | NA
- "Diff" não existe na linha do líder (gap zero fica em branco no PDF);
- o nome pode ter espaços e barra ("L.ROSA / L.JUNIOR", "C.RIBAS/R.FILHO");
- na variante BY CLASS a numeração de posição reinicia a cada classe.

Por causa do nome com espaços, a linha é lida DE TRÁS PRA FRENTE: os últimos
campos são numéricos e bem definidos (NA, [Diff], Best Tm, Laps, Classe), e o
que sobrar entre o nº do carro e a classe é o nome. Campo que não casar com o
formato esperado gera aviso e a linha é descartada — nunca adivinhada.
"""

import re
from typing import Optional

import pdfplumber
from pydantic import BaseModel, Field

from app.parser.laptimes_parser import (
    _converter_tempo_para_segundos,
    _extrair_palavras_da_pagina,
)
from app.parser.tipo_pdf import MetadadosSessao, _extrair_metadados, _linhas_de_texto

_RE_TEMPO = re.compile(r"^\d+:\d{2}\.\d{3}$|^\d+\.\d{3}$")
_RE_INT = re.compile(r"^\d+$")


class PilotoResumo(BaseModel):
    """Uma linha do resumo oficial."""

    posicao: int = Field(..., description="Posição no ranking (na variante BY CLASS, dentro da classe).")
    numero_carro: str
    nome: str
    classe: str = Field(..., description="Classe/categoria, ex: ELITE ou MASTER.")
    voltas: int
    melhor_volta_s: float
    diff_s: Optional[float] = Field(None, description="Gap para o líder. None na linha do líder.")
    volta_da_melhor: Optional[int] = Field(None, description="Coluna NA: volta em que fez a melhor marca.")


class ResumoQualify(BaseModel):
    arquivo_origem: str
    agrupado_por_classe: bool
    metadados: Optional[dict] = None
    pilotos: list[PilotoResumo] = Field(default_factory=list)
    avisos: list[str] = Field(default_factory=list)


def parse_qualify_pdf(caminho_pdf: str, agrupado_por_classe: bool) -> ResumoQualify:
    avisos: list[str] = []
    pilotos: list[PilotoResumo] = []

    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            palavras = _extrair_palavras_da_pagina(pagina)
            for linha in _linhas_de_texto(palavras):
                piloto = _parse_linha(linha.strip(), avisos)
                if piloto is not None:
                    pilotos.append(piloto)

    if not pilotos:
        avisos.append("Nenhuma linha de piloto reconhecida no resumo.")

    meta: MetadadosSessao = _extrair_metadados_do_arquivo(caminho_pdf)
    return ResumoQualify(
        arquivo_origem=caminho_pdf,
        agrupado_por_classe=agrupado_por_classe,
        metadados=meta.__dict__,
        pilotos=pilotos,
        avisos=avisos,
    )


def _extrair_metadados_do_arquivo(caminho_pdf: str) -> MetadadosSessao:
    with pdfplumber.open(caminho_pdf) as pdf:
        palavras = _extrair_palavras_da_pagina(pdf.pages[0])
    return _extrair_metadados(_linhas_de_texto(palavras))


def _parse_linha(linha: str, avisos: list[str]) -> Optional[PilotoResumo]:
    """
    Tenta interpretar uma linha como linha de piloto. Linhas de cabeçalho,
    rodapé e seção de classe simplesmente não casam e retornam None (sem
    aviso — só linhas que PARECEM de piloto mas falham geram aviso).
    """
    tokens = linha.split()
    # Formato mínimo: pos carro nome classe laps best na  -> 7 tokens
    if len(tokens) < 7:
        return None
    if not (_RE_INT.match(tokens[0]) and _RE_INT.match(tokens[1])):
        return None  # não começa com "pos carro" — não é linha de piloto

    # Fim da linha, de trás pra frente: NA, [Diff], Best Tm, Laps.
    cauda = list(tokens)
    try:
        na = int(cauda.pop()) if _RE_INT.match(cauda[-1]) else None
        if na is None:
            cauda.pop()  # célula NA ilegível: descarta o token mesmo assim

        diff: Optional[float] = None
        if _RE_TEMPO.match(cauda[-1]) and ":" not in cauda[-1] and _RE_TEMPO.match(cauda[-2]):
            # penúltimo é o Best Tm (tem ':'), último é o Diff (só segundos)
            diff = _converter_tempo_para_segundos(cauda.pop())

        melhor_txt = cauda.pop()
        melhor = _converter_tempo_para_segundos(melhor_txt)
        if melhor is None:
            avisos.append(f"Linha ignorada (Best Tm ilegível '{melhor_txt}'): {linha[:60]}")
            return None

        voltas_txt = cauda.pop()
        if not _RE_INT.match(voltas_txt):
            avisos.append(f"Linha ignorada (Laps ilegível '{voltas_txt}'): {linha[:60]}")
            return None

        classe = cauda.pop()
        posicao, carro = int(cauda[0]), cauda[1]
        nome = " ".join(cauda[2:]).strip()
        if not nome or not classe.isupper():
            avisos.append(f"Linha ignorada (nome/classe não reconhecidos): {linha[:60]}")
            return None

        return PilotoResumo(
            posicao=posicao,
            numero_carro=carro,
            nome=nome,
            classe=classe,
            voltas=int(voltas_txt),
            melhor_volta_s=melhor,
            diff_s=diff,
            volta_da_melhor=na,
        )
    except (IndexError, ValueError):
        avisos.append(f"Linha ignorada (formato inesperado): {linha[:60]}")
        return None

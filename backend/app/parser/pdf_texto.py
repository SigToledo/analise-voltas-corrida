"""
Leitura de baixo nível dos PDFs de cronometragem (compartilhada por todos os
parsers): palavras com posição, limpeza do "falso negrito", agrupamento em
linhas e corte do rodapé.

Convenção de coordenadas (a mesma do pdfplumber): `x0`/`x1` são as bordas
esquerda/direita da palavra e `top` é a distância do TOPO da página, em
pontos (1 pt = 1/72 de polegada).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import pdfplumber


@dataclass(frozen=True)
class Palavra:
    texto: str
    x0: float
    x1: float
    top: float
    destaque: bool = False
    """Impressa em NEGRITO. O cronômetro destaca assim a melhor volta OFICIAL e
    os melhores setores de cada piloto — seja com fonte bold de verdade
    (Cascavel), seja com o "falso negrito" de texto impresso várias vezes
    (Cuiabá)."""

    @property
    def x_centro(self) -> float:
        return (self.x0 + self.x1) / 2.0


# Palavras que marcam o começo do RODAPÉ dos relatórios Orbits (assinaturas,
# crédito do sistema, data de impressão). Nada abaixo delas é dado de tabela.
ANCORAS_RODAPE = frozenset({"Chief", "Orbits", "www.mylaps.com", "Printed:"})


def _remover_falso_negrito(chars: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    O cronômetro imprime valores em destaque 3-4 vezes quase na mesma posição
    para simular negrito. Sem limpar, "48.415" vira "44448888....444411115555".
    Mantemos só a primeira cópia de cada caractere (mesmo texto a <1pt).

    Devolve (mantidos, com_copia): `com_copia` são os caracteres mantidos que
    TINHAM cópias — é assim que reconhecemos o destaque do falso negrito.

    Usa um índice por célula de 1pt em vez de comparar cada caractere com
    todos os anteriores: fica linear no número de caracteres (os relatórios de
    corrida têm dezenas de milhares). Como uma cópia a <1pt pode cair na célula
    vizinha, conferimos as 9 células ao redor.
    """
    indice: dict[tuple[str, int, int], list[dict]] = {}
    mantidos: list[dict] = []
    com_copia: dict[int, dict] = {}
    for c in chars:
        cx, cy = int(c["x0"]), int(c["top"])
        original = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for v in indice.get((c["text"], cx + dx, cy + dy), ()):
                    if abs(v["x0"] - c["x0"]) < 1.0 and abs(v["top"] - c["top"]) < 1.0:
                        original = v
                        break
                if original is not None:
                    break
            if original is not None:
                break
        if original is None:
            indice.setdefault((c["text"], cx, cy), []).append(c)
            mantidos.append(c)
        else:
            com_copia[id(original)] = original
    return mantidos, list(com_copia.values())


def extrair_palavras(pagina) -> list[Palavra]:
    """Palavras da página (pdfplumber), sem o falso negrito e com o destaque marcado."""
    limpos, com_copia = _remover_falso_negrito(pagina.chars)
    ids = {id(c) for c in limpos}
    filtrada = pagina.filter(
        lambda obj: id(obj) in ids if obj.get("object_type") == "char" else True
    )
    # Posições (arredondadas) dos caracteres impressos em "falso negrito".
    copias = {(round(c["x0"]), round(c["top"])) for c in com_copia}
    palavras = []
    for w in filtrada.extract_words(
        use_text_flow=False, keep_blank_chars=False, extra_attrs=["fontname"]
    ):
        negrito_real = "bold" in w["fontname"].lower()
        falso_negrito = any(
            (round(x), round(w["top"]) + dy) in copias
            for x in (w["x0"], w["x0"] + 1)
            for dy in (-1, 0, 1)
        )
        palavras.append(
            Palavra(
                texto=w["text"], x0=w["x0"], x1=w["x1"], top=w["top"],
                destaque=negrito_real or falso_negrito,
            )
        )
    return palavras


def agrupar_linhas(palavras: list[Palavra], tolerancia: float = 3.0) -> list[list[Palavra]]:
    """
    Agrupa palavras em linhas pela proximidade VERTICAL: uma palavra entra na
    linha atual se estiver a até `tolerancia` pt do topo da PRIMEIRA palavra da
    linha. (Arredondar o `top` para uma grade, como antes, partia uma mesma
    linha em duas quando as palavras caíam em lados opostos de uma fronteira.)

    A tolerância de 3pt também junta os valores de uma mesma volta que o PDF
    imprime em duas "sublinhas" desalinhadas em 1-2pt.
    Cada linha volta ordenada da esquerda para a direita.
    """
    linhas: list[list[Palavra]] = []
    for p in sorted(palavras, key=lambda w: w.top):
        if linhas and p.top - linhas[-1][0].top <= tolerancia:
            linhas[-1].append(p)
        else:
            linhas.append([p])
    return [sorted(linha, key=lambda w: w.x0) for linha in linhas]


def celulas(linha: list[Palavra], vao: float = 12.0) -> list[str]:
    """
    Divide uma linha em "células" de texto: palavras separadas por um vão
    horizontal maior que `vao` pt pertencem a células diferentes. Serve para o
    cabeçalho da sessão, onde o PDF põe duas informações na mesma altura
    (ex.: nome da sessão à esquerda e a data à direita).
    """
    resultado: list[list[str]] = []
    anterior: Palavra | None = None
    for p in linha:
        if anterior is None or p.x0 - anterior.x1 > vao:
            resultado.append([p.texto])
        else:
            resultado[-1].append(p.texto)
        anterior = p
    return [" ".join(c) for c in resultado]


def limite_rodape(palavras: list[Palavra]) -> float:
    """`top` onde o rodapé começa (infinito se não houver âncora)."""
    tops = [p.top for p in palavras if p.texto in ANCORAS_RODAPE]
    return min(tops) if tops else float("inf")


class LeitorPDF:
    """
    Abre o PDF UMA vez e guarda as palavras de cada página (já limpas e sem
    rodapé). A detecção de tipo e o parser reutilizam a mesma leitura — antes
    o mesmo arquivo era aberto e limpo 2-3 vezes por requisição.
    """

    def __init__(self, caminho: str):
        self.caminho = caminho
        self._pdf = pdfplumber.open(caminho)
        self._cache: dict[int, list[Palavra]] = {}

    def __enter__(self) -> "LeitorPDF":
        return self

    def __exit__(self, *_exc) -> None:
        self.fechar()

    def fechar(self) -> None:
        self._pdf.close()

    @cached_property
    def num_paginas(self) -> int:
        return len(self._pdf.pages)

    def palavras(self, indice: int, com_rodape: bool = False) -> list[Palavra]:
        """Palavras da página `indice` (0 = primeira). Sem o rodapé, por padrão."""
        if indice not in self._cache:
            self._cache[indice] = extrair_palavras(self._pdf.pages[indice])
        todas = self._cache[indice]
        if com_rodape:
            return todas
        corte = limite_rodape(todas)
        return [p for p in todas if p.top < corte]

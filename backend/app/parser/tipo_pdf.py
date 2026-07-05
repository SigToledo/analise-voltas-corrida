"""
Detecção do TIPO de relatório PDF e extração dos metadados do cabeçalho.

A equipe recebe três relatórios da mesma sessão (sistema Orbits/MyLaps):

1. "Laptimes"  — volta a volta, com setores e radar. Tem o cabeçalho de
   tabela "Lap  Lap Tm  S1 Tm ... SSTRAP" e a linha "Practice (mm:ss Time)".
2. "QualifyReduced" — resumo geral (Pos, No., Name, Class, Laps, Best Tm,
   Diff, NA). Tem o selo "Sorted on best lap time" no topo.
3. "QualifyReduced BY CLASS" — mesmo resumo, mas agrupado por classe
   (ELITE / MASTER), com o nome da classe numa linha própria e a numeração
   de posição reiniciando dentro de cada classe.

Cada tipo pede um parser diferente — alimentar o parser errado produziria
lixo silencioso, então a detecção vem ANTES de qualquer parsing.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pdfplumber

from app.parser.laptimes_parser import _extrair_palavras_da_pagina


class TipoPDF(str, Enum):
    LAPTIMES = "laptimes"
    QUALIFY = "qualify"
    QUALIFY_POR_CLASSE = "qualify_por_classe"
    DESCONHECIDO = "desconhecido"


@dataclass
class MetadadosSessao:
    """Cabeçalho comum aos três relatórios (extraído, nunca inventado)."""

    evento: Optional[str] = None        # ex: "ET4 - F TRUCK / MBR - 2026"
    pista: Optional[str] = None         # ex: "AUTODROMO DE CUIABA 4,500 km"
    sessao: Optional[str] = None        # ex: "4o TREINO OFICIAL MBR - GRUPO 1"
    data_hora: Optional[str] = None     # ex: "13/06/2026 08:00"
    duracao: Optional[str] = None       # ex: "Practice (30:00 Time) started at 9:13:13"


def _linhas_de_texto(palavras) -> list[str]:
    """Agrupa as palavras da página em linhas de texto simples (por altura)."""
    linhas: dict[int, list] = {}
    for p in palavras:
        chave = round(p.top / 4)  # tolerância de ~4pt agrupa a mesma linha
        linhas.setdefault(chave, []).append(p)
    resultado = []
    for chave in sorted(linhas):
        ordenadas = sorted(linhas[chave], key=lambda w: w.x0)
        resultado.append(" ".join(w.texto for w in ordenadas))
    return resultado


def detectar_tipo_pdf(caminho_pdf: str) -> tuple[TipoPDF, MetadadosSessao]:
    """
    Lê APENAS a primeira página e decide qual dos três relatórios é,
    devolvendo junto os metadados do cabeçalho.
    """
    with pdfplumber.open(caminho_pdf) as pdf:
        palavras = _extrair_palavras_da_pagina(pdf.pages[0])

    linhas = _linhas_de_texto(palavras)
    texto = "\n".join(linhas)
    meta = _extrair_metadados(linhas)

    tem_laptimes = "Lap Tm" in texto and "SSTRAP" in texto
    tem_resumo = "Sorted on best lap time" in texto or (
        "Best Tm" in texto and "Diff" in texto
    )

    if tem_laptimes:
        return TipoPDF.LAPTIMES, meta

    if tem_resumo:
        # BY CLASS: alguma linha é SÓ o nome de uma classe (seção do grupo).
        # No resumo plano, a classe aparece sempre no meio da linha do piloto.
        for linha in linhas:
            candidata = linha.strip()
            if candidata and candidata.isupper() and " " not in candidata and len(candidata) <= 12:
                # linha curta, toda maiúscula, sem espaços — cabeçalho de classe
                # (ex: "ELITE", "MASTER"). Cabeçalhos gerais como "MBR" também
                # casam, então exigimos que ela apareça TAMBÉM como coluna de
                # classe em alguma linha de piloto.
                if any(f" {candidata} " in outra for outra in linhas if outra != linha):
                    return TipoPDF.QUALIFY_POR_CLASSE, meta
        return TipoPDF.QUALIFY, meta

    return TipoPDF.DESCONHECIDO, meta


def _extrair_metadados(linhas: list[str]) -> MetadadosSessao:
    """
    Extrai o cabeçalho comum. As linhas típicas (na ordem do PDF):
      "ET4 - F TRUCK / MBR - 2026"           -> evento
      "MBR AUTODROMO DE CUIABA 4,500 km"     -> pista (após o nome do camp.)
      "4o TREINO OFICIAL MBR - GRUPO 1 13/06/2026 08:00" -> sessão + data
      "Practice (30:00 Time) started at 9:13:13"          -> duração
    O layout junta células vizinhas na mesma linha, então usamos âncoras
    (padrões como "km", data dd/mm/aaaa) em vez de posições fixas.
    """
    import re

    meta = MetadadosSessao()
    for linha in linhas[:12]:  # só o cabeçalho; a tabela vem depois
        limpa = linha.strip()
        if meta.evento is None and re.search(r"\b\d{4}\b", limpa) and " - " in limpa and "km" not in limpa:
            meta.evento = limpa
            continue
        m = re.search(r"([A-ZÀ-Ú][A-ZÀ-Ú .]+ [\d.,]+ km)", limpa)
        if meta.pista is None and m:
            meta.pista = m.group(1).strip()
            continue
        m = re.search(r"^(.*?)\s*(\d{2}/\d{2}/\d{4}(?: \d{2}:\d{2})?)\s*$", limpa)
        if meta.sessao is None and m and m.group(1).strip():
            meta.sessao = m.group(1).strip()
            meta.data_hora = m.group(2)
            continue
        if meta.duracao is None and "started at" in limpa:
            meta.duracao = limpa
    return meta

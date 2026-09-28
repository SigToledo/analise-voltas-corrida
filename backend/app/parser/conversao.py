"""
Conversão dos textos do PDF para números. Tudo que não casar EXATAMENTE com
um formato conhecido devolve None — quem chama decide como sinalizar. Nunca
"adivinhamos" um valor a partir de texto estranho.
"""

from __future__ import annotations

import re

_RE_SEGUNDOS = re.compile(r"^\d+\.\d+$")                     # 49.994
_RE_MIN_SEG = re.compile(r"^(\d+):(\d{2}\.\d+)$")            # 2:23.983
_RE_H_MIN_SEG = re.compile(r"^(\d+):(\d{2}):(\d{2}\.\d+)$")  # 1:05:13.349
_RE_VELOCIDADE = re.compile(r"^\d+[.,]\d+$|^\d+$")           # 180,3 | 180.3 | 180
_RE_INTEIRO = re.compile(r"^\d+$")
_RE_VOLTAS_ATRAS = re.compile(r"^(\d+) (?:Laps?|L)$")         # "1 Lap", "2 Laps"


def tempo_em_segundos(texto: str | None) -> float | None:
    """'49.994' → 49.994 ; '2:23.983' → 143.983 ; '1:05:13.349' → 3913.349.

    Arredonda ao milésimo (a precisão do cronômetro): somar 60 + 19.79 em ponto
    flutuante dá 79.78999999999999, que é o mesmo número mas polui a saída.
    """
    if texto is None:
        return None
    t = texto.strip()
    if _RE_SEGUNDOS.match(t):
        return round(float(t), 3)
    m = _RE_MIN_SEG.match(t)
    if m:
        return round(int(m.group(1)) * 60 + float(m.group(2)), 3)
    m = _RE_H_MIN_SEG.match(t)
    if m:
        return round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 3)
    return None


def velocidade_kmh(texto: str | None) -> float | None:
    """'180,3' → 180.3 (vírgula decimal, padrão BR) ; também aceita ponto."""
    if texto is None or not _RE_VELOCIDADE.match(texto.strip()):
        return None
    return float(texto.strip().replace(",", "."))


def inteiro(texto: str | None) -> int | None:
    if texto is None or not _RE_INTEIRO.match(texto.strip()):
        return None
    return int(texto.strip())


def voltas_atras(texto: str | None) -> int | None:
    """'1 Lap' → 1 ; '2 Laps' → 2 (diferença em voltas, em resultado de corrida)."""
    if texto is None:
        return None
    m = _RE_VOLTAS_ATRAS.match(texto.strip())
    return int(m.group(1)) if m else None

"""
Leitura da LINHA DE CABEÇALHO das tabelas (títulos das colunas) e
distribuição dos valores de uma linha de dados entre as colunas.

Os relatórios de cronometragem são configuráveis: cada evento escolhe quais
colunas aparecem e em que ordem (ex.: em Cuiabá o radar se chama "SSTRAP", em
Cascavel "SPD"; o resumo de Cascavel tem "Gap" e "Total Tm", o de Cuiabá não).
Por isso os parsers NÃO dependem da posição/ordem das colunas: eles leem os
títulos e casam cada valor com a coluna pelo alinhamento — regra conferida em
todos os modelos de relatório disponíveis (Cuiabá e Cascavel, 5 categorias):
- colunas NUMÉRICAS alinham pela borda DIREITA do título (o tempo "1:17.257"
  termina 2-8pt antes do fim de "Best Tm");
- colunas de TEXTO (nome, classe) alinham pela borda ESQUERDA do título e
  ocupam o espaço até a coluna seguinte.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.parser.pdf_texto import Palavra

# Pares de palavras que formam um único título.
_PARES_COMPOSTOS = {
    ("In", "Lap"), ("In", "Session"), ("Total", "points"), ("Overall", "BestTm"),
}
# Vão máximo (pt) entre as palavras de um mesmo título.
_VAO_MAXIMO_TITULO = 6.0

# Títulos de colunas de TEXTO (alinhadas à esquerda). O resto é numérico.
TITULOS_TEXTO = frozenset({"Name", "Class", "Classe", "Carro", "EQUIPE", "Equipe", "Team"})

# Nomes que a coluna de velocidade de radar recebe conforme o evento.
TITULOS_RADAR = frozenset({"SSTRAP", "SPD", "Speed", "SPEED", "Spd", "TopSpeed"})

_RE_SETOR = re.compile(r"^S(\d+) Tm$")
_RE_INTEIRO = re.compile(r"^\d+$")
_RE_VOLTAS_ATRAS = re.compile(r"^(Laps?|L)$")

# Distância mínima entre o fim de uma coluna de texto e o título seguinte:
# valores numéricos (alinhados à direita) costumam começar ANTES do título.
_RECUO_FIM_TEXTO = 8.0
_FOLGA_INICIO_TEXTO = 4.0


@dataclass(frozen=True)
class Coluna:
    titulo: str
    x0: float
    x1: float

    @property
    def eh_texto(self) -> bool:
        return self.titulo in TITULOS_TEXTO

    @property
    def eh_radar(self) -> bool:
        return self.titulo in TITULOS_RADAR

    @property
    def numero_setor(self) -> int | None:
        """1 para "S1 Tm", 2 para "S2 Tm"… None se não for coluna de setor."""
        m = _RE_SETOR.match(self.titulo)
        return int(m.group(1)) if m else None


def ler_titulos(linha: list[Palavra]) -> list[Coluna]:
    """
    Converte as palavras da linha de cabeçalho em colunas com título:
    "Best"+"Tm" → "Best Tm", "In"+"Lap" → "In Lap"… Só junta palavras coladas
    (vão ≤ 6pt), para nunca fundir duas colunas vizinhas.
    """
    colunas: list[Coluna] = []
    palavras = sorted(linha, key=lambda w: w.x0)
    i = 0
    while i < len(palavras):
        atual = palavras[i]
        prox = palavras[i + 1] if i + 1 < len(palavras) else None
        colado = prox is not None and prox.x0 - atual.x1 <= _VAO_MAXIMO_TITULO
        if colado and (prox.texto == "Tm" or (atual.texto, prox.texto) in _PARES_COMPOSTOS):
            colunas.append(Coluna(f"{atual.texto} {prox.texto}", atual.x0, prox.x1))
            i += 2
        else:
            colunas.append(Coluna(atual.texto, atual.x0, atual.x1))
            i += 1
    return colunas


def coluna_numerica_mais_proxima(
    valor: Palavra, colunas: list[Coluna], tolerancia: float = 12.0
) -> Coluna | None:
    """
    Coluna numérica cujo título termina mais perto de onde o valor termina
    (alinhamento pela direita). None se nenhuma estiver a até `tolerancia` pt:
    o valor NÃO é encaixado à força em coluna nenhuma.
    """
    candidatas = [c for c in colunas if not c.eh_texto]
    if not candidatas:
        return None
    melhor = min(candidatas, key=lambda c: abs(c.x1 - valor.x1))
    return melhor if abs(melhor.x1 - valor.x1) <= tolerancia else None


def _faixas_de_texto(colunas: list[Coluna]) -> list[tuple[Coluna, float, float]]:
    """Faixa horizontal [início, fim) de cada coluna de texto."""
    ordenadas = sorted(colunas, key=lambda c: c.x0)
    faixas = []
    for i, col in enumerate(ordenadas):
        if not col.eh_texto:
            continue
        fim = ordenadas[i + 1].x0 - _RECUO_FIM_TEXTO if i + 1 < len(ordenadas) else float("inf")
        faixas.append((col, col.x0 - _FOLGA_INICIO_TEXTO, fim))
    return faixas


def _juntar_voltas_atras(linha: list[Palavra]) -> list[Palavra]:
    """
    Em resultado de corrida, quem está uma volta atrás aparece com "1 Lap" na
    coluna de diferença — duas palavras que precisam virar UM valor, senão o
    "1" e o "Lap" poderiam ser distribuídos em colunas diferentes.
    """
    resultado: list[Palavra] = []
    for p in linha:
        anterior = resultado[-1] if resultado else None
        if (
            anterior is not None
            and _RE_VOLTAS_ATRAS.match(p.texto)
            and _RE_INTEIRO.match(anterior.texto)
            and p.x0 - anterior.x1 <= _VAO_MAXIMO_TITULO
        ):
            resultado[-1] = Palavra(f"{anterior.texto} {p.texto}", anterior.x0, p.x1, anterior.top)
        else:
            resultado.append(p)
    return resultado


@dataclass
class LinhaDistribuida:
    """Valores de uma linha de dados por título de coluna (texto cru)."""

    valores: dict[str, str]
    sem_coluna: list[str]      # palavras que não casaram com coluna alguma
    conflitos: list[str]       # colunas numéricas que receberam 2+ valores


def distribuir_linha(linha: list[Palavra], colunas: list[Coluna]) -> LinhaDistribuida:
    """
    Distribui as palavras de uma linha de dados entre as colunas do cabeçalho:
    palavra dentro da faixa de uma coluna de texto → texto (nomes com várias
    palavras são reunidos); o resto → coluna numérica pela borda direita.
    Colunas numéricas que recebem dois valores são reportadas como conflito —
    quem chama decide descartar, nunca "escolhe" um dos valores.
    """
    faixas = _faixas_de_texto(colunas)
    textos: dict[str, list[str]] = {}
    numeros: dict[str, list[str]] = {}
    sem_coluna: list[str] = []

    for p in _juntar_voltas_atras(sorted(linha, key=lambda w: w.x0)):
        faixa = next((c for c, ini, fim in faixas if ini <= p.x0 < fim), None)
        if faixa is not None:
            textos.setdefault(faixa.titulo, []).append(p.texto)
            continue
        col = coluna_numerica_mais_proxima(p, colunas)
        if col is None:
            sem_coluna.append(p.texto)
        else:
            numeros.setdefault(col.titulo, []).append(p.texto)

    valores = {t: " ".join(v) for t, v in textos.items()}
    conflitos = [t for t, v in numeros.items() if len(v) > 1]
    valores.update({t: v[0] for t, v in numeros.items() if len(v) == 1})
    return LinhaDistribuida(valores=valores, sem_coluna=sem_coluna, conflitos=conflitos)

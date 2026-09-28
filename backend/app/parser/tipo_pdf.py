"""
Identificação do RELATÓRIO (qual PDF é) e da SESSÃO (treino, qualy, corrida),
mais os metadados do cabeçalho.

Uma etapa gera muitos relatórios (Orbits/MyLaps). O app analisa:
- LAPTIMES: volta a volta, com setores e radar — a fonte da análise;
- RESUMO: "QualifyReduced" de treino/qualy (ranking por melhor volta);
- RESULTADO_CORRIDA: "RaceFull" (classificação final da prova).
Os demais (consolidado, pódio, parcial por hora, grid de largada, lapchart)
são reconhecidos para dar uma mensagem clara, mas não analisados.

A identificação vem ANTES de qualquer parsing: alimentar o parser errado
produziria lixo silencioso. Ela usa os TÍTULOS da tabela (não o nome do
arquivo, que o usuário pode renomear) e a linha da sessão ("Practice (...)",
"Qualifying (...)", "Race (...)").
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum

from app.parser.cabecalho import Coluna, ler_titulos
from app.parser.pdf_texto import LeitorPDF, Palavra, agrupar_linhas, celulas


class TipoRelatorio(str, Enum):
    LAPTIMES = "laptimes"
    RESUMO = "resumo"
    RESULTADO_CORRIDA = "resultado_corrida"
    NAO_SUPORTADO = "nao_suportado"
    DESCONHECIDO = "desconhecido"


class TipoSessao(str, Enum):
    TREINO = "treino"
    QUALY = "qualy"
    CORRIDA = "corrida"


NOMES_RELATORIO = {
    TipoRelatorio.LAPTIMES: "Laptimes (volta a volta)",
    TipoRelatorio.RESUMO: "resumo QualifyReduced",
    TipoRelatorio.RESULTADO_CORRIDA: "resultado de corrida (RaceFull)",
    TipoRelatorio.NAO_SUPORTADO: "relatório não suportado",
    TipoRelatorio.DESCONHECIDO: "formato não reconhecido",
}


@dataclass
class MetadadosSessao:
    """Cabeçalho comum aos relatórios (extraído, nunca inventado)."""

    evento: str | None = None       # ex: "FORMULA TRUCK - MBR | CASCAVEL 2026"
    etapa: str | None = None        # ex: "5ET - MBR"
    pista: str | None = None        # ex: "Autódromo Zilmar Beux Cascavel 3,058 km"
    sessao: str | None = None       # ex: "1º TREINO OFICIAL MBR - GRUPO 1"
    data_hora: str | None = None    # ex: "11/09/2026 08:45"
    duracao: str | None = None      # ex: "Practice (20:00 Time) started at 9:05:33"
    tipo_sessao: TipoSessao | None = None

    def como_dict(self) -> dict:
        d = asdict(self)
        d["tipo_sessao"] = self.tipo_sessao.value if self.tipo_sessao else None
        return d


@dataclass
class Identificacao:
    tipo: TipoRelatorio
    metadados: MetadadosSessao
    agrupado_por_classe: bool = False
    detalhe: str | None = None      # ex: "consolidado de sessões" (p/ não suportados)


_RE_LINHA_SESSAO = re.compile(r"^(Practice|Qualifying|Race)\b.*(\(|started)")
_RE_DATA = re.compile(r"^\d{2}/\d{2}/\d{4}( \d{1,2}:\d{2})?$")


def tipo_sessao_de(duracao: str | None, nome_sessao: str | None) -> TipoSessao | None:
    """
    Tipo da sessão pela linha "Practice/Qualifying/Race (...)". Classificatórios
    às vezes rodam como "Practice" no cronômetro — o nome da sessão
    ("CLASSIFICATORIO", "TOP QUALIFYING") desempata. Sem nenhuma pista, None.
    """
    nome = (nome_sessao or "").upper()
    parece_qualy = "CLASSIF" in nome or "QUALIF" in nome
    if duracao:
        if duracao.startswith("Race"):
            return TipoSessao.CORRIDA
        if duracao.startswith("Qualifying") or parece_qualy:
            return TipoSessao.QUALY
        return TipoSessao.TREINO
    if "CORRIDA" in nome or "RACE" in nome:
        return TipoSessao.CORRIDA
    if parece_qualy:
        return TipoSessao.QUALY
    if "TREINO" in nome or "WARM" in nome or "PRACTICE" in nome:
        return TipoSessao.TREINO
    return None


def extrair_metadados(linhas_acima: list[list[Palavra]]) -> MetadadosSessao:
    """
    Metadados a partir das linhas ACIMA da tabela, lidas célula a célula (o
    PDF põe duas informações na mesma altura, ex.: nome da sessão à esquerda e
    data à direita). Reconhece cada informação pelo formato, não pela posição.
    """
    meta = MetadadosSessao()
    for linha in linhas_acima:
        cels = [c for c in celulas(linha) if not c.startswith("Sorted on")]
        if not cels:
            continue
        texto = " ".join(cels)
        if meta.duracao is None and _RE_LINHA_SESSAO.match(texto):
            meta.duracao = texto
            continue
        pista = next((c for c in cels if re.search(r"\bkm$", c)), None)
        if pista and meta.pista is None:
            meta.pista = pista
            outras = [c for c in cels if c != pista]
            meta.etapa = outras[0] if outras else None
            continue
        data = next((c for c in cels if _RE_DATA.match(c)), None)
        if data and meta.data_hora is None:
            meta.data_hora = data
            outras = [c for c in cels if c != data]
            meta.sessao = " ".join(outras) or None
            continue
        if meta.evento is None and re.search(r"\b\d{4}\b", texto):
            meta.evento = cels[0]
    meta.tipo_sessao = tipo_sessao_de(meta.duracao, meta.sessao)
    return meta


def localizar_cabecalho(linhas: list[list[Palavra]]) -> tuple[int, list[Coluna]] | None:
    """Índice e colunas da linha de títulos da tabela (a 1ª com "Lap Tm" ou "Pos")."""
    for i, linha in enumerate(linhas):
        colunas = ler_titulos(linha)
        titulos = {c.titulo for c in colunas}
        if "Lap Tm" in titulos or (colunas and colunas[0].titulo == "Pos"):
            return i, colunas
    return None


def _tem_secoes_de_classe(linhas_dados: list[list[Palavra]], colunas: list[Coluna]) -> bool:
    """
    BY CLASS: entre as linhas de pilotos aparecem linhas com SÓ o nome da
    classe ("ELITE", "MASTER"), começando à esquerda da coluna "No.".
    """
    col_no = next((c for c in colunas if c.titulo in ("No.", "No")), None)
    limite = col_no.x0 if col_no else 60.0
    for linha in linhas_dados:
        if 1 <= len(linha) <= 3 and linha[0].x0 < limite and not any(
            ch.isdigit() for p in linha for ch in p.texto
        ):
            return True
    return False


def identificar(leitor: LeitorPDF) -> Identificacao:
    """Identifica o relatório pela 1ª página (títulos da tabela + linha da sessão)."""
    linhas = agrupar_linhas(leitor.palavras(0))
    achado = localizar_cabecalho(linhas)
    if achado is None:
        meta = extrair_metadados(linhas[:6])
        return Identificacao(TipoRelatorio.DESCONHECIDO, meta)

    indice, colunas = achado
    meta = extrair_metadados(linhas[:indice])
    titulos = {c.titulo for c in colunas}

    if "Lap Tm" in titulos and any(c.numero_setor for c in colunas):
        return Identificacao(TipoRelatorio.LAPTIMES, meta)
    if "Total points" in titulos:
        return Identificacao(TipoRelatorio.NAO_SUPORTADO, meta, detalhe="pontuação do pódio")
    if "In Session" in titulos or "Overall BestTm" in titulos:
        return Identificacao(TipoRelatorio.NAO_SUPORTADO, meta, detalhe="consolidado de sessões")
    if "Last Tm" in titulos:
        return Identificacao(TipoRelatorio.NAO_SUPORTADO, meta, detalhe="parcial da corrida")
    if "Best Tm" in titulos:
        por_classe = _tem_secoes_de_classe(linhas[indice + 1 :], colunas)
        tipo = (
            TipoRelatorio.RESULTADO_CORRIDA
            if meta.tipo_sessao is TipoSessao.CORRIDA
            else TipoRelatorio.RESUMO
        )
        return Identificacao(tipo, meta, agrupado_por_classe=por_classe)
    return Identificacao(TipoRelatorio.DESCONHECIDO, meta)

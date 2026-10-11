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

Um ARQUIVO pode trazer mais de um relatório: o documento oficial compilado
("RESULTADO - CLASSIFICATÓRIO", assinado pelos comissários) junta resumo e
Laptimes de duas sessões num PDF só. `desmontar` separa o arquivo nos
relatórios que ele contém, identificando página a página.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum

from app.parser.cabecalho import Coluna, ler_titulos
from app.parser.pdf_texto import FontePaginas, LeitorPDF, Palavra, TrechoPDF, agrupar_linhas, celulas


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


# Títulos de seção que o Orbits imprime no meio da tabela e que NÃO são
# classes. Sem esta lista, "Announcements" (comunicados, no fim da página)
# fazia todo resumo de Cascavel parecer BY CLASS — e a posição oficial era
# descartada —, e os carros depois de "Not classified" herdavam isso como
# classe.
SECOES_NAO_CLASSE = {
    "not classified", "non classified", "announcements", "did not start",
    "did not finish", "disqualified", "excluded",
}
# Depois deste título só vem texto livre (comunicados da direção de prova):
# nenhuma linha dali é piloto.
SECOES_FIM_DA_TABELA = {"announcements"}


def titulo_de_secao(linha: list[Palavra], colunas: list[Coluna]) -> str | None:
    """
    Linha curta, só com texto, começando à esquerda da coluna "No.": um
    título de seção ("ELITE", "Not classified", "Announcements"). None se a
    linha é de dados.
    """
    col_no = next((c for c in colunas if c.titulo in ("No.", "No", "Nº")), None)
    limite = col_no.x0 if col_no else 60.0
    if 1 <= len(linha) <= 3 and linha[0].x0 < limite and not any(
        ch.isdigit() for p in linha for ch in p.texto
    ):
        return " ".join(p.texto for p in linha)
    return None


def _tem_secoes_de_classe(linhas_dados: list[list[Palavra]], colunas: list[Coluna]) -> bool:
    """
    BY CLASS: entre as linhas de pilotos aparecem linhas com SÓ o nome da
    classe ("ELITE", "MASTER"), começando à esquerda da coluna "No.".
    """
    for linha in linhas_dados:
        titulo = titulo_de_secao(linha, colunas)
        if titulo is None:
            continue
        if titulo.lower() in SECOES_FIM_DA_TABELA:
            return False
        if titulo.lower() not in SECOES_NAO_CLASSE:
            return True
    return False


def identificar(leitor: FontePaginas) -> Identificacao:
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


@dataclass
class Relatorio:
    """Um relatório dentro de um arquivo: o que ele é e em quais páginas está."""

    ident: Identificacao
    paginas: list[int]              # índices no PDF (0 = primeira página)

    def descricao_paginas(self) -> str:
        """'pág. 2–3' ou 'pág. 6', na numeração que o usuário vê no PDF."""
        primeira, ultima = self.paginas[0] + 1, self.paginas[-1] + 1
        return f"pág. {primeira}" if primeira == ultima else f"pág. {primeira}–{ultima}"


def _mesmo_relatorio(a: Identificacao, b: Identificacao) -> bool:
    """Mesmo tipo de tabela e mesma sessão (nome + horário do cabeçalho)."""
    return (a.tipo, a.metadados.sessao, a.metadados.data_hora) == (
        b.tipo, b.metadados.sessao, b.metadados.data_hora,
    )


def _sem_tabela(pagina: TrechoPDF) -> bool:
    """Página sem nenhuma linha de títulos (capa, texto, página em branco)."""
    return localizar_cabecalho(agrupar_linhas(pagina.palavras(0))) is None


def desmontar(leitor: LeitorPDF) -> list[Relatorio]:
    """
    Separa o arquivo nos relatórios que ele contém. Toda página do cronômetro
    repete o próprio cabeçalho (títulos da tabela, nome e horário da sessão),
    então cada página é identificada sozinha, e as páginas SEGUIDAS com o
    mesmo tipo e a mesma sessão formam um relatório. Ex.: o RESULTADO do
    classificatório da Truck (Tarumã) vira 5 relatórios — resumo e Laptimes do
    Classificatório, resumo e Laptimes do Top Qualifying, e o consolidado.

    Página sem tabela nenhuma no meio do arquivo continua o relatório
    anterior: é o que acontecia antes (o parser a pula com aviso).

    Conferido nos 120 PDFs de samples/: todo relatório avulso do cronômetro
    vira UM relatório, igual à identificação pela 1ª página — só o documento
    compilado se divide.
    """
    relatorios: list[Relatorio] = []
    for n in range(leitor.num_paginas):
        pagina = TrechoPDF(leitor, [n])
        ident = identificar(pagina)
        anterior = relatorios[-1] if relatorios else None
        if anterior is not None and (
            _mesmo_relatorio(anterior.ident, ident)
            or (ident.tipo is TipoRelatorio.DESCONHECIDO and _sem_tabela(pagina))
        ):
            anterior.paginas.append(n)
        else:
            relatorios.append(Relatorio(ident, [n]))
    return relatorios

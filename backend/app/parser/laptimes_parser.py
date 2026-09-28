"""
Parser do relatório "Laptimes" (Orbits/MyLaps): todas as voltas de cada
piloto, com tempo total, setores e velocidade de radar.

----------------------------------------------------------------------
COMO O PDF É MONTADO (conferido em Cuiabá e Cascavel, 5 categorias)
----------------------------------------------------------------------
1. Cada página tem DUAS colunas de pilotos lado a lado. A linha de títulos
   repete o mesmo conjunto para cada uma:
       Lap | Lap Tm | S1 Tm | S2 Tm | S3 Tm | SPD      (Cascavel)
       Lap | Lap Tm | S1 Tm | S2 Tm | S3 Tm | SSTRAP   (Cuiabá)
   Por isso lemos os TÍTULOS: o número de setores e o nome do radar variam
   por evento. Cada grupo de colunas começa num título "Lap" isolado.

2. Leitura em SERPENTINA: coluna esquerda de cima a baixo, depois a direita,
   depois a próxima página. Um piloto que começa no fim de uma coluna
   CONTINUA no topo da seguinte, sem repetir o cabeçalho "(número) nome".

3. Cada valor encontra sua coluna pelo alinhamento com o título: valores
   numéricos terminam 2-8pt antes do fim do título (ver cabecalho.py). Valor
   que não casa com coluna nenhuma é descartado com aviso — nunca encaixado
   à força. É isso que protege contra um setor a mais ou a menos.

4. Os valores de uma volta saem em duas "sublinhas" desalinhadas em 1-2pt; o
   agrupamento de linhas (pdf_texto.agrupar_linhas) junta as duas. As linhas
   são agrupadas POR COLUNA DE PILOTOS, para uma coluna não bagunçar a outra.

5. "p" antes do número da volta = volta de entrada no box. Às vezes o PDF
   separa o "p" do número ("p" + "7"); um "p" sozinho marca a volta seguinte.

6. Volta de SAÍDA de box (volta 1 ou a seguinte a uma "p"): o cronômetro não
   conta parte do tempo parado no box, então o total sai irreal. Marcamos aqui,
   junto do dado bruto; a análise decide como tratar.

REGRA DE OURO: valor ausente ou ilegível fica None e entra em
`campos_ausentes` (ou nos avisos). Nunca preenchemos com 0 ou estimativa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.lap_data import PilotoLaps, ResultadoParsingPDF, VoltaLeitura
from app.parser.cabecalho import Coluna, coluna_numerica_mais_proxima
from app.parser.conversao import tempo_em_segundos, velocidade_kmh
from app.parser.pdf_texto import LeitorPDF, Palavra, agrupar_linhas
from app.parser.tipo_pdf import localizar_cabecalho

PADRAO_CABECALHO_PILOTO = re.compile(r"^\((\d+)\)$")      # "(171)"
PADRAO_NUMERO_VOLTA = re.compile(r"^p?(\d+)$", re.IGNORECASE)  # "7" ou "p7"
_RE_NUMERICO = re.compile(r"^[\d:.,]+$")                 # tempos, inteiros, velocidades

# O cabeçalho "(171) L.JOSE" começa até ~20pt à esquerda do título "Lap" da
# sua coluna; a margem decide a qual coluna de pilotos uma palavra pertence.
_MARGEM_INICIO_GRUPO = 25.0


@dataclass
class _Grupo:
    """Uma coluna de pilotos da página e os títulos das suas colunas."""

    indice: int
    colunas: list[Coluna]
    numero: Coluna                      # "Lap" (número da volta)
    tempo: Coluna | None                # "Lap Tm"
    setores: list[Coluna]               # "S1 Tm", "S2 Tm"… em ordem
    radar: Coluna | None                # "SPD" / "SSTRAP"…

    @property
    def inicio(self) -> float:
        return self.numero.x0


def _montar_grupos(colunas: list[Coluna]) -> list[_Grupo]:
    """Divide a linha de títulos em colunas de pilotos (cada uma começa num "Lap")."""
    blocos: list[list[Coluna]] = []
    for c in colunas:
        if c.titulo == "Lap":
            blocos.append([c])
        elif blocos:
            blocos[-1].append(c)
    grupos = []
    for i, cols in enumerate(blocos):
        grupos.append(
            _Grupo(
                indice=i,
                colunas=cols,
                numero=cols[0],
                tempo=next((c for c in cols if c.titulo == "Lap Tm"), None),
                setores=sorted((c for c in cols if c.numero_setor), key=lambda c: c.numero_setor),
                radar=next((c for c in cols if c.eh_radar), None),
            )
        )
    return grupos


def _grupo_pela_posicao(x0: float, grupos: list[_Grupo]) -> _Grupo:
    """Coluna de pilotos mais à direita que começa antes da palavra (com margem)."""
    candidatos = [g for g in grupos if g.inicio <= x0 + _MARGEM_INICIO_GRUPO]
    return max(candidatos, key=lambda g: g.inicio) if candidatos else grupos[0]


@dataclass
class _Estado:
    """O que o parser 'lembra' enquanto percorre o PDF na ordem de leitura."""

    num_setores: int
    pilotos: dict[tuple[str, str], PilotoLaps] = field(default_factory=dict)
    piloto_atual: PilotoLaps | None = None
    volta_atual: VoltaLeitura | None = None
    definidos: set[str] = field(default_factory=set)    # campos já lidos na volta atual
    pit_pendente: bool = False
    classe_atual: str | None = None
    avisos: list[str] = field(default_factory=list)
    colunas_ignoradas: set[str] = field(default_factory=set)

    def ref(self) -> str:
        p = self.piloto_atual
        v = self.volta_atual
        quem = f"({p.numero_carro}) {p.nome}" if p else "sem piloto"
        return f"{quem}, volta {v.numero_volta}" if v else quem


def _definir(estado: _Estado, campo: str, valor, texto: str) -> None:
    """Grava um campo na volta atual. Dois valores no mesmo campo = conflito:
    o campo fica None e vira aviso (nunca escolhemos um dos dois)."""
    volta = estado.volta_atual
    if campo in estado.definidos:
        estado.avisos.append(f"{estado.ref()}: dois valores para {campo} — descartado.")
        valor = None
    elif valor is None:
        estado.avisos.append(f"{estado.ref()}: {campo} ilegível ('{texto}').")
    estado.definidos.add(campo)
    if campo.startswith("setor"):
        indice = int(campo[5:-2]) - 1
        volta.setores_s[indice] = valor
    else:
        setattr(volta, campo, valor)


def _processar_valor(estado: _Estado, grupo: _Grupo, p: Palavra) -> None:
    if p.texto.lower() == "p":
        estado.pit_pendente = True
        return
    col = coluna_numerica_mais_proxima(p, grupo.colunas)
    if col is None:
        estado.avisos.append(f"{estado.ref()}: valor '{p.texto}' sem coluna correspondente — ignorado.")
        return

    if col is grupo.numero:
        m = PADRAO_NUMERO_VOLTA.match(p.texto)
        if not m:
            estado.avisos.append(f"{estado.ref()}: número de volta ilegível ('{p.texto}').")
            return
        if estado.piloto_atual is None:
            estado.avisos.append(f"Volta '{p.texto}' antes de qualquer piloto — ignorada.")
            return
        estado.volta_atual = VoltaLeitura(
            numero_volta=int(m.group(1)),
            eh_volta_pit=p.texto.lower().startswith("p") or estado.pit_pendente,
            setores_s=[None] * estado.num_setores,
        )
        estado.piloto_atual.voltas.append(estado.volta_atual)
        estado.definidos = set()
        estado.pit_pendente = False
        return

    if estado.volta_atual is None:
        estado.avisos.append(f"{estado.ref()}: valor '{p.texto}' antes do número da volta — ignorado.")
        return

    if col is grupo.tempo:
        _definir(estado, "tempo_volta_s", tempo_em_segundos(p.texto), p.texto)
        if p.destaque:
            estado.volta_atual.melhor_oficial = True
    elif col in grupo.setores:
        _definir(estado, f"setor{col.numero_setor}_s", tempo_em_segundos(p.texto), p.texto)
    elif col is grupo.radar:
        _definir(estado, "velocidade_radar_kmh", velocidade_kmh(p.texto), p.texto)
    elif col.titulo not in estado.colunas_ignoradas:
        estado.colunas_ignoradas.add(col.titulo)
        estado.avisos.append(f"Coluna '{col.titulo}' não é usada pela análise — valores ignorados.")


def _processar_linha(estado: _Estado, grupo: _Grupo, linha: list[Palavra]) -> None:
    cab = next((i for i, p in enumerate(linha) if PADRAO_CABECALHO_PILOTO.match(p.texto)), None)
    if cab is not None:
        numero = PADRAO_CABECALHO_PILOTO.match(linha[cab].texto).group(1)
        nome_partes = [p.texto for p in linha[cab + 1 :] if not _RE_NUMERICO.match(p.texto)]
        nome = " ".join(nome_partes).strip()
        if not nome:
            estado.avisos.append(f"Cabeçalho '({numero})' sem nome legível — ignorado.")
            return
        chave = (numero, nome)
        if chave not in estado.pilotos:
            estado.pilotos[chave] = PilotoLaps(numero_carro=numero, nome=nome, classe=estado.classe_atual)
        estado.piloto_atual = estado.pilotos[chave]
        estado.volta_atual = None
        estado.pit_pendente = False
        for p in linha[cab + 1 :]:
            if _RE_NUMERICO.match(p.texto):
                _processar_valor(estado, grupo, p)
        return

    so_texto = all(
        not _RE_NUMERICO.match(p.texto)
        and p.texto.lower() != "p"
        and not PADRAO_NUMERO_VOLTA.match(p.texto)
        for p in linha
    )
    if so_texto and len(linha) <= 3:
        # Linha curta só com texto e sem piloto: rótulo de seção (Laptimes
        # "by class" traz o nome da classe entre os blocos de pilotos).
        estado.classe_atual = " ".join(p.texto for p in linha)
        return

    for p in linha:
        _processar_valor(estado, grupo, p)


def _palavras_por_grupo(corpo: list[Palavra], grupos: list[_Grupo]) -> dict[int, list[Palavra]]:
    """Separa as palavras do corpo da tabela por coluna de pilotos."""
    colunas_todas = [c for g in grupos for c in g.colunas]
    grupo_da_coluna = {c: g for g in grupos for c in g.colunas}
    por_grupo: dict[int, list[Palavra]] = {g.indice: [] for g in grupos}
    for p in corpo:
        grupo = None
        if _RE_NUMERICO.match(p.texto):
            col = coluna_numerica_mais_proxima(p, colunas_todas)
            grupo = grupo_da_coluna[col] if col else None
        if grupo is None:
            grupo = _grupo_pela_posicao(p.x0, grupos)
        por_grupo[grupo.indice].append(p)
    return por_grupo


def parse_laptimes(leitor: LeitorPDF, nome_arquivo: str | None = None) -> ResultadoParsingPDF:
    """Lê todas as páginas do Laptimes na ordem de leitura (serpentina)."""
    estado: _Estado | None = None
    esquema: tuple[int, bool] | None = None   # (nº de setores, tem radar) da 1ª página
    avisos_pagina: list[str] = []

    for n in range(leitor.num_paginas):
        palavras = leitor.palavras(n)
        linhas = agrupar_linhas(palavras)
        achado = localizar_cabecalho(linhas)
        if achado is None:
            avisos_pagina.append(f"Página {n + 1}: sem linha de títulos (Lap, Lap Tm…) — ignorada.")
            continue
        indice, colunas = achado
        grupos = _montar_grupos(colunas)
        if not grupos or grupos[0].tempo is None:
            avisos_pagina.append(f"Página {n + 1}: títulos sem 'Lap'/'Lap Tm' — ignorada.")
            continue

        esta = (len(grupos[0].setores), grupos[0].radar is not None)
        if esquema is None:
            esquema = esta
            estado = _Estado(num_setores=esta[0])
        elif esta != esquema:
            avisos_pagina.append(
                f"Página {n + 1}: colunas diferentes da 1ª página ({esta} vs {esquema}) — ignorada."
            )
            continue

        topo_cabecalho = max(p.top for p in linhas[indice])
        corpo = [p for p in palavras if p.top > topo_cabecalho + 2]
        por_grupo = _palavras_por_grupo(corpo, grupos)
        for grupo in grupos:                       # esquerda, depois direita
            estado.volta_atual = None              # nada de valor "vazar" entre colunas
            for linha in agrupar_linhas(por_grupo[grupo.indice]):
                _processar_linha(estado, grupo, linha)

    if estado is None:
        return ResultadoParsingPDF(
            arquivo_origem=nome_arquivo or leitor.caminho,
            avisos=avisos_pagina or ["Nenhuma página com tabela de voltas."],
        )

    num_setores, tem_radar = esquema
    for piloto in estado.pilotos.values():
        pits = {v.numero_volta for v in piloto.voltas if v.eh_volta_pit}
        for v in piloto.voltas:
            v.eh_volta_saida_box = v.numero_volta == 1 or (v.numero_volta - 1) in pits
            ausentes = [] if v.tempo_volta_s is not None else ["tempo_volta_s"]
            ausentes += [f"setor{i + 1}_s" for i, s in enumerate(v.setores_s) if s is None]
            if tem_radar and v.velocidade_radar_kmh is None:
                ausentes.append("velocidade_radar_kmh")
            v.campos_ausentes = ausentes

    return ResultadoParsingPDF(
        arquivo_origem=nome_arquivo or leitor.caminho,
        num_setores=num_setores,
        tem_radar=tem_radar,
        pilotos=[p for p in estado.pilotos.values() if p.voltas],
        avisos=avisos_pagina + estado.avisos,
    )


def parse_laptimes_pdf(caminho_pdf: str) -> ResultadoParsingPDF:
    """Atalho: abre o arquivo e faz o parsing (usado em testes e scripts)."""
    with LeitorPDF(caminho_pdf) as leitor:
        return parse_laptimes(leitor)

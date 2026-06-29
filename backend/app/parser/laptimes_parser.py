"""
Parser do PDF "Laptimes_sec4" (sistema de cronometragem Orbits/MyLaps).

----------------------------------------------------------------------
COMO O PDF É MONTADO (o que descobrimos inspecionando os PDFs reais)
----------------------------------------------------------------------

1. Cada página tem DUAS colunas de pilotos lado a lado: uma "coluna esquerda"
   (mais ou menos entre x=0 e x=280) e uma "coluna direita" (x > 280).

2. Dentro de cada coluna, os pilotos aparecem em sequência, um bloco depois
   do outro. Cada bloco começa com uma linha "(NUMERO_CARRO) NOME" e depois
   tem uma linha por volta.

3. Cada linha de volta tem até 6 valores: número da volta, Lap Tm (tempo
   total da volta), S1 Tm, S2 Tm, S3 Tm e SSTRAP (velocidade de radar).
   PORÉM esses 6 valores nem sempre ficam todos na mesma "linha de texto":
   o PDF foi gerado de um jeito que às vezes quebra os valores de uma volta
   em duas linhas de texto muito próximas verticalmente (1 a 2 pontos de
   diferença). Por isso NÃO podemos confiar em "uma linha de texto = uma
   volta" — temos que agrupar por proximidade vertical (mesma "linha lógica").

4. O PDF também imprime alguns números em destaque (a melhor volta/setor de
   cada coluna) repetindo o mesmo texto 3-4 vezes com um deslocamento de
   1/100 de ponto para simular efeito de negrito (não é fonte bold real).
   Se a gente não tratar isso, a extração de texto simples (PyPDF2, ou até
   pdfplumber sem cuidado) cola essas cópias quase coincidentes e produz
   lixo do tipo "44448888....444411115555" em vez de "48.415". Por isso
   ANTES de extrair palavras, removemos caracteres duplicados que ocupam
   quase a mesma posição (função `_remover_caracteres_duplicados`).

5. Cada coluna (esquerda/direita) tem suas próprias posições X fixas para
   cada campo (Lap, Lap Tm, S1, S2, S3, SSTRAP). Descobrimos essas posições
   inspecionando o cabeçalho da tabela em cada coluna. Em vez de assumir
   "o primeiro número da linha é X", associamos cada valor lido à coluna
   mais próxima dele em X — isso é o que garante a associação correta
   volta -> tempo mesmo quando faltam valores no meio.

6. Voltas de entrada/saída de boxes vêm marcadas com prefixo "p" no número
   da volta (ex: "p5"). Essas voltas frequentemente têm setores faltando
   (o carro passou por baixo do pórtico de cronometragem de forma diferente).
   Marcamos eh_volta_pit=True e deixamos os campos que não vieram como None.

----------------------------------------------------------------------
REGRA DE OURO: NUNCA INVENTAR DADO
----------------------------------------------------------------------
Se um valor esperado (S1, S2, S3, Lap Tm ou SSTRAP) não for encontrado para
uma volta, o campo correspondente fica None e o nome do campo é adicionado
em `campos_ausentes` daquela volta. Nunca preenchemos com 0.0 ou qualquer
estimativa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pdfplumber

from app.models.lap_data import PilotoLaps, ResultadoParsingPDF, VoltaLeitura

# Tolerância vertical (em pontos do PDF) para considerar que duas palavras
# pertencem à mesma "linha lógica" de volta. Descobrimos inspecionando os
# PDFs que a quebra entre as duas linhas físicas de uma mesma volta é de
# 1 a 2 pontos — por isso usamos uma faixa um pouco maior pra segurança.
TOLERANCIA_VERTICAL_MESMA_LINHA = 3.0

# Tolerância horizontal para "esse valor pertence a essa coluna de campo".
# As posições X de cada campo são bem regulares no PDF (mesma fonte,
# colunas alinhadas), então uma tolerância pequena já é suficiente e evita
# associar um valor à coluna vizinha por erro.
TOLERANCIA_HORIZONTAL_COLUNA = 12.0

# Ponto de corte em X que separa a coluna esquerda da coluna direita de
# pilotos, válido para todas as páginas inspecionadas deste relatório.
LIMITE_X_COLUNA_DIREITA = 280.0

# Padrão de cabeçalho de piloto: "(numero) NOME" -- ex: "(171) L.JOSE" ou
# "(899) A.MARTINS/V.MARTENDAL".
PADRAO_CABECALHO_PILOTO = re.compile(r"^\((\d+)\)$")

# Padrão de número de volta, com ou sem prefixo de pit "p".
PADRAO_NUMERO_VOLTA = re.compile(r"^p?(\d+)$", re.IGNORECASE)


@dataclass
class _PosicoesColuna:
    """Posições X (centro aproximado) de cada campo, para uma coluna de pilotos."""

    x_numero_volta: float
    x_lap_tm: float
    x_s1: float
    x_s2: float
    x_s3: float
    x_sstrap: float


@dataclass
class _Palavra:
    texto: str
    x0: float
    x1: float
    top: float

    @property
    def x_centro(self) -> float:
        return (self.x0 + self.x1) / 2.0


def _remover_caracteres_duplicados(chars: list[dict]) -> list[dict]:
    """
    Remove caracteres que o PDF imprime várias vezes na (quase) mesma
    posição para simular negrito. Mantemos só a primeira ocorrência de
    cada (texto, posição aproximada).

    Sem isso, palavras como "48.415" viram "44448888....444411115555"
    quando extraídas, porque pdfplumber concatena as 3-4 cópias quase
    coincidentes em uma só "palavra".
    """
    vistos: list[dict] = []
    resultado: list[dict] = []
    for c in chars:
        eh_duplicado = False
        for v in vistos:
            if (
                v["text"] == c["text"]
                and abs(v["x0"] - c["x0"]) < 1.0
                and abs(v["top"] - c["top"]) < 1.0
            ):
                eh_duplicado = True
                break
        if not eh_duplicado:
            vistos.append(c)
            resultado.append(c)
    return resultado


def _extrair_palavras_da_pagina(page) -> list[_Palavra]:
    """Extrai as palavras da página já com os caracteres duplicados removidos."""
    chars_limpos = _remover_caracteres_duplicados(page.chars)
    chars_limpos_ids = {id(c) for c in chars_limpos}
    pagina_filtrada = page.filter(
        lambda obj: id(obj) in chars_limpos_ids if obj.get("object_type") == "char" else True
    )
    palavras_brutas = pagina_filtrada.extract_words(use_text_flow=False, keep_blank_chars=False)
    return [
        _Palavra(texto=w["text"], x0=w["x0"], x1=w["x1"], top=w["top"]) for w in palavras_brutas
    ]


def _agrupar_por_linha_logica(palavras: list[_Palavra]) -> list[list[_Palavra]]:
    """
    Agrupa palavras cujo `top` está dentro da tolerância vertical, formando
    uma "linha lógica". Isso resolve o caso em que uma mesma volta tem seus
    valores espalhados em duas linhas de texto físicas muito próximas.
    """
    palavras_ordenadas = sorted(palavras, key=lambda p: p.top)
    linhas: list[list[_Palavra]] = []
    for palavra in palavras_ordenadas:
        if linhas and (palavra.top - linhas[-1][0].top) <= TOLERANCIA_VERTICAL_MESMA_LINHA:
            linhas[-1].append(palavra)
        else:
            linhas.append([palavra])
    return linhas


def _detectar_posicoes_colunas(palavras: list[_Palavra]) -> dict[str, _PosicoesColuna]:
    """
    Lê a linha de cabeçalho ("Lap Lap Tm S1 Tm S2 Tm S3 Tm SSTRAP") de cada
    coluna (esquerda/direita) e devolve as posições X de cada campo.

    Não fixamos essas posições "no código" como números mágicos isolados:
    nós as calculamos a partir do próprio PDF a cada parsing, porque a
    posição exata pode variar um pouco entre relatórios diferentes (fonte,
    margens). Isso torna o parser um pouco mais robusto a pequenas
    variações de layout dentro do mesmo formato "Laptimes_sec4".
    """
    candidatas_lap = [p for p in palavras if p.texto == "Lap" and p.top < 200]
    candidatas_tm = [p for p in palavras if p.texto == "Tm" and p.top < 200]
    candidatas_sstrap = [p for p in palavras if p.texto == "SSTRAP" and p.top < 200]

    posicoes: dict[str, _PosicoesColuna] = {}

    # Importante: os valores numéricos no PDF são alinhados pela borda
    # DIREITA da coluna (alinhamento "à direita", comum em colunas
    # numéricas), e não pela borda esquerda do texto do cabeçalho. Por
    # isso usamos sempre `x1` (fim da palavra) tanto do cabeçalho quanto,
    # depois, dos valores -- e não `x0` (início).
    for lado, limite_min, limite_max in (
        ("esquerda", 0.0, LIMITE_X_COLUNA_DIREITA),
        ("direita", LIMITE_X_COLUNA_DIREITA, 10_000.0),
    ):
        laps_do_lado = sorted(
            (p for p in candidatas_lap if limite_min <= p.x0 < limite_max), key=lambda p: p.x0
        )
        tms_do_lado = sorted(
            (p for p in candidatas_tm if limite_min <= p.x0 < limite_max), key=lambda p: p.x0
        )
        sstrap_do_lado = [p for p in candidatas_sstrap if limite_min <= p.x0 < limite_max]
        if len(laps_do_lado) < 2 or len(tms_do_lado) < 4 or not sstrap_do_lado:
            # Não conseguimos achar o cabeçalho completo dessa coluna nesta
            # página — isso é sinalizado como aviso pelo chamador, e essa
            # coluna simplesmente não será processada nesta página.
            continue

        # A primeira palavra "Lap" é a coluna do número da volta (não tem
        # "Tm" associado). As 4 ocorrências de "Tm" (na ordem em x) são,
        # respectivamente: Lap Tm, S1 Tm, S2 Tm, S3 Tm.
        x_numero_volta = laps_do_lado[0].x1
        x_lap_tm, x_s1, x_s2, x_s3 = (p.x1 for p in tms_do_lado[:4])

        posicoes[lado] = _PosicoesColuna(
            x_numero_volta=x_numero_volta,
            x_lap_tm=x_lap_tm,
            x_s1=x_s1,
            x_s2=x_s2,
            x_s3=x_s3,
            x_sstrap=sstrap_do_lado[0].x1,
        )

    return posicoes


def _coluna_da_palavra(x0: float) -> str:
    return "direita" if x0 >= LIMITE_X_COLUNA_DIREITA else "esquerda"


def _campo_mais_proximo(x1: float, posicoes: _PosicoesColuna) -> str | None:
    """
    Decide a qual campo (numero_volta / lap_tm / s1 / s2 / s3 / sstrap) um
    valor numérico pertence, com base na distância da borda direita (x1)
    dele até a borda direita de cada campo (descoberta a partir do
    cabeçalho da coluna). Usamos x1 e não x0 porque os números no PDF são
    alinhados pela direita dentro de cada coluna.

    Retorna None se a distância mínima for maior que a tolerância aceita
    — nesse caso o valor é descartado e um aviso é gerado, em vez de
    "forçar" uma associação que pode estar errada.
    """
    candidatos = {
        "numero_volta": posicoes.x_numero_volta,
        "lap_tm": posicoes.x_lap_tm,
        "s1": posicoes.x_s1,
        "s2": posicoes.x_s2,
        "s3": posicoes.x_s3,
        "sstrap": posicoes.x_sstrap,
    }
    # min() devolve a tupla (nome_do_campo, posicao_x_do_campo). A distância
    # que nos interessa é |posicao_x_do_campo - x1|, calculada à parte — não
    # confundir com a própria posição_x devolvida na tupla.
    campo_mais_proximo, x_do_campo = min(
        candidatos.items(), key=lambda item: abs(item[1] - x1)
    )
    if abs(x_do_campo - x1) <= TOLERANCIA_HORIZONTAL_COLUNA:
        return campo_mais_proximo
    return None


def _converter_tempo_para_segundos(texto: str) -> float | None:
    """
    Converte um tempo no formato do PDF para segundos (float).

    Formatos vistos no PDF real:
      - "49.994"   -> 49.994 segundos (sem minutos)
      - "2:23.983" -> 2 minutos e 23.983 segundos = 143.983 segundos
      - "1:04.160" -> 1 minuto e 4.160 segundos = 64.160 segundos

    Se o texto não bater com nenhum desses formatos, devolve None (em vez
    de tentar adivinhar) — quem chamou essa função decide como sinalizar.
    """
    texto = texto.strip()
    if re.fullmatch(r"\d+:\d{2}\.\d+", texto):
        minutos_str, resto = texto.split(":")
        try:
            return int(minutos_str) * 60 + float(resto)
        except ValueError:
            return None
    if re.fullmatch(r"\d+\.\d+", texto):
        try:
            return float(texto)
        except ValueError:
            return None
    return None


def _converter_velocidade(texto: str) -> float | None:
    """
    Converte a velocidade de radar para float. No PDF ela vem com vírgula
    como separador decimal (ex: "180,3"), então convertemos para ponto
    antes de fazer o float().
    """
    texto = texto.strip()
    if re.fullmatch(r"\d+,\d+", texto):
        try:
            return float(texto.replace(",", "."))
        except ValueError:
            return None
    return None


@dataclass
class _BlocoPiloto:
    numero_carro: str
    nome: str
    coluna: str
    top_inicio: float
    top_fim: float | None = None  # preenchido depois (top do próximo piloto da mesma coluna, ou infinito)


def _identificar_blocos_de_pilotos(linhas_logicas: list[list[_Palavra]]) -> list[_BlocoPiloto]:
    """
    Percorre as linhas lógicas procurando o padrão de cabeçalho de piloto
    "(numero) NOME..." em cada coluna, e devolve a lista de blocos, cada um
    com o intervalo vertical (top_inicio, top_fim) onde suas voltas estão.
    """
    blocos: list[_BlocoPiloto] = []

    for linha in linhas_logicas:
        linha_ordenada = sorted(linha, key=lambda p: p.x0)
        for i, palavra in enumerate(linha_ordenada):
            m = PADRAO_CABECALHO_PILOTO.match(palavra.texto)
            if not m:
                continue
            numero_carro = m.group(1)
            coluna = _coluna_da_palavra(palavra.x0)
            # O nome é formado pelas palavras seguintes na mesma linha que
            # ainda estão na mesma coluna (não atravessam para a coluna
            # vizinha) -- no formato real do PDF, "(171)" e "L.JOSE" estão
            # sempre na mesma linha física.
            partes_nome = []
            for outra in linha_ordenada[i + 1 :]:
                if _coluna_da_palavra(outra.x0) != coluna:
                    break
                partes_nome.append(outra.texto)
            nome = " ".join(partes_nome).strip()
            if not nome:
                # Cabeçalho sem nome legível -- não temos como confiar que
                # isso é mesmo um cabeçalho de piloto válido sem inventar
                # um nome. Ignoramos esse "candidato".
                continue
            blocos.append(
                _BlocoPiloto(
                    numero_carro=numero_carro,
                    nome=nome,
                    coluna=coluna,
                    top_inicio=palavra.top,
                )
            )

    # Define o fim de cada bloco como o início do próximo bloco da MESMA
    # coluna (ou infinito, se for o último bloco daquela coluna na página).
    for coluna in ("esquerda", "direita"):
        blocos_da_coluna = sorted(
            (b for b in blocos if b.coluna == coluna), key=lambda b: b.top_inicio
        )
        for i, bloco in enumerate(blocos_da_coluna):
            if i + 1 < len(blocos_da_coluna):
                bloco.top_fim = blocos_da_coluna[i + 1].top_inicio
            else:
                bloco.top_fim = float("inf")

    return blocos


def _extrair_voltas_do_bloco(
    bloco: _BlocoPiloto,
    linhas_logicas: list[list[_Palavra]],
    posicoes_colunas: dict[str, _PosicoesColuna],
    avisos: list[str],
) -> list[VoltaLeitura]:
    """
    Para um bloco de piloto já identificado (intervalo vertical conhecido),
    percorre as linhas lógicas dentro desse intervalo, na coluna certa, e
    monta uma VoltaLeitura por número de volta encontrado.
    """
    posicoes = posicoes_colunas.get(bloco.coluna)
    if posicoes is None:
        avisos.append(
            f"Piloto ({bloco.numero_carro}) {bloco.nome}: não foi possível detectar as "
            f"posições de coluna ({bloco.coluna}) nesta página — bloco ignorado."
        )
        return []

    voltas: list[VoltaLeitura] = []
    volta_atual: VoltaLeitura | None = None

    for linha in linhas_logicas:
        palavras_do_bloco = [
            p
            for p in linha
            if bloco.top_inicio < p.top < bloco.top_fim and _coluna_da_palavra(p.x0) == bloco.coluna
        ]
        if not palavras_do_bloco:
            continue

        for palavra in sorted(palavras_do_bloco, key=lambda p: p.x0):
            campo = _campo_mais_proximo(palavra.x1, posicoes)
            if campo is None:
                avisos.append(
                    f"Piloto ({bloco.numero_carro}) {bloco.nome}: valor '{palavra.texto}' em "
                    f"x={palavra.x0:.1f} não pôde ser associado a nenhuma coluna conhecida — ignorado."
                )
                continue

            if campo == "numero_volta":
                m = PADRAO_NUMERO_VOLTA.match(palavra.texto)
                if not m:
                    avisos.append(
                        f"Piloto ({bloco.numero_carro}) {bloco.nome}: número de volta "
                        f"ilegível ('{palavra.texto}') — volta ignorada."
                    )
                    continue
                if volta_atual is not None:
                    voltas.append(volta_atual)
                volta_atual = VoltaLeitura(
                    numero_volta=int(m.group(1)),
                    eh_volta_pit=palavra.texto.lower().startswith("p"),
                )
                continue

            if volta_atual is None:
                # Achamos um S1/S2/S3/Lap Tm/SSTRAP antes de qualquer número
                # de volta nesse bloco -- não deveria acontecer no layout
                # esperado. Sinalizamos e ignoramos o valor solto.
                avisos.append(
                    f"Piloto ({bloco.numero_carro}) {bloco.nome}: valor de '{campo}' "
                    f"('{palavra.texto}') encontrado sem volta associada — ignorado."
                )
                continue

            if campo == "sstrap":
                valor = _converter_velocidade(palavra.texto)
                if valor is None:
                    avisos.append(
                        f"Piloto ({bloco.numero_carro}) {bloco.nome}, volta "
                        f"{volta_atual.numero_volta}: SSTRAP ilegível ('{palavra.texto}')."
                    )
                else:
                    volta_atual.velocidade_radar_kmh = valor
                continue

            # lap_tm / s1 / s2 / s3 -> tempos no formato min:seg ou seg
            valor = _converter_tempo_para_segundos(palavra.texto)
            if valor is None:
                avisos.append(
                    f"Piloto ({bloco.numero_carro}) {bloco.nome}, volta "
                    f"{volta_atual.numero_volta}: tempo ilegível em '{campo}' ('{palavra.texto}')."
                )
                continue

            if campo == "lap_tm":
                volta_atual.tempo_volta_s = valor
            elif campo == "s1":
                volta_atual.setor1_s = valor
            elif campo == "s2":
                volta_atual.setor2_s = valor
            elif campo == "s3":
                volta_atual.setor3_s = valor

    if volta_atual is not None:
        voltas.append(volta_atual)

    # Marca explicitamente quais campos faltaram em cada volta, em vez de
    # deixar isso implícito (None). Isso facilita muito quem for usar esse
    # resultado depois (ex: mostrar um aviso visual no frontend).
    nomes_dos_campos = {
        "tempo_volta_s": "tempo_volta_s",
        "setor1_s": "setor1_s",
        "setor2_s": "setor2_s",
        "setor3_s": "setor3_s",
        "velocidade_radar_kmh": "velocidade_radar_kmh",
    }
    for volta in voltas:
        volta.campos_ausentes = [
            nome for nome in nomes_dos_campos if getattr(volta, nome) is None
        ]

    return voltas


def _topo_do_cabecalho_tabela(palavras: list[_Palavra]) -> float | None:
    """
    Devolve o `top` (altura) da linha de cabeçalho da tabela ("Lap Lap Tm S1
    Tm ... SSTRAP"), usando a palavra "SSTRAP" como âncora. Serve para saber
    a partir de que altura começam as linhas de volta numa coluna — qualquer
    volta acima do primeiro cabeçalho de piloto, mas abaixo desse cabeçalho de
    tabela, é uma VOLTA DE CONTINUAÇÃO (ver explicação em parse_laptimes_pdf).
    """
    tops_sstrap = [p.top for p in palavras if p.texto == "SSTRAP" and p.top < 200]
    if not tops_sstrap:
        return None
    return min(tops_sstrap)


def parse_laptimes_pdf(caminho_pdf: str) -> ResultadoParsingPDF:
    """
    Função principal do parser. Recebe o caminho de um PDF no formato
    "Laptimes_sec4" e devolve um ResultadoParsingPDF com os dados de todos
    os pilotos encontrados, mais uma lista de avisos sobre qualquer dado
    que não pôde ser lido com confiança.

    ----------------------------------------------------------------------
    ORDEM DE LEITURA E VOLTAS DE CONTINUAÇÃO
    ----------------------------------------------------------------------
    O relatório NÃO é "duas colunas independentes por página". É um fluxo
    único que serpenteia: coluna esquerda (de cima a baixo), depois coluna
    direita, depois a próxima página, e assim por diante. Um piloto pode
    começar no fim de uma coluna e CONTINUAR no topo da coluna seguinte —
    e nessa continuação o PDF NÃO repete o cabeçalho "(numero) nome".

    Por isso processamos as colunas nessa ordem de leitura e guardamos o
    "piloto em andamento" (`piloto_atual`). Quando uma coluna tem linhas de
    volta acima do seu primeiro cabeçalho de piloto, essas voltas são a
    continuação do `piloto_atual` (o último piloto visto antes desta coluna),
    e não um piloto novo. Sem isso, pilotos cujo bloco cruza a quebra de
    coluna/página perderiam parte das voltas.
    """
    avisos: list[str] = []
    pilotos_por_chave: dict[tuple[str, str], PilotoLaps] = {}
    # Mantém a ordem em que os pilotos aparecem no PDF (dict preserva inserção).

    def _obter_piloto(numero_carro: str, nome: str) -> PilotoLaps:
        chave = (numero_carro, nome)
        piloto = pilotos_por_chave.get(chave)
        if piloto is None:
            piloto = PilotoLaps(numero_carro=numero_carro, nome=nome, voltas=[])
            pilotos_por_chave[chave] = piloto
        return piloto

    # Chave do último piloto visto na ordem de leitura, para adotar as voltas
    # de continuação no topo da próxima coluna. None no começo do documento.
    piloto_atual: tuple[str, str] | None = None

    with pdfplumber.open(caminho_pdf) as pdf:
        for indice_pagina, page in enumerate(pdf.pages):
            palavras = _extrair_palavras_da_pagina(page)
            if not palavras:
                avisos.append(f"Página {indice_pagina + 1}: nenhum texto extraído.")
                continue

            linhas_logicas = _agrupar_por_linha_logica(palavras)
            posicoes_colunas = _detectar_posicoes_colunas(palavras)
            if not posicoes_colunas:
                avisos.append(
                    f"Página {indice_pagina + 1}: não foi possível detectar o cabeçalho "
                    f"da tabela (Lap/Lap Tm/S1/S2/S3/SSTRAP) — página ignorada."
                )
                continue

            topo_tabela = _topo_do_cabecalho_tabela(palavras)
            # Início da zona de continuação: logo abaixo do cabeçalho da tabela.
            # +2 pontos evita pegar as próprias palavras do cabeçalho.
            topo_continuacao = (topo_tabela + 2.0) if topo_tabela is not None else 0.0

            blocos = _identificar_blocos_de_pilotos(linhas_logicas)
            if not blocos:
                avisos.append(
                    f"Página {indice_pagina + 1}: nenhum cabeçalho de piloto "
                    f"'(numero) nome' encontrado."
                )
                continue

            # Processa coluna esquerda e depois direita (ordem de leitura).
            for coluna in ("esquerda", "direita"):
                if coluna not in posicoes_colunas:
                    continue
                blocos_coluna = sorted(
                    (b for b in blocos if b.coluna == coluna), key=lambda b: b.top_inicio
                )

                # (1) Voltas de continuação: acima do 1º cabeçalho desta coluna.
                topo_primeiro_cabecalho = (
                    blocos_coluna[0].top_inicio if blocos_coluna else float("inf")
                )
                if piloto_atual is not None and topo_primeiro_cabecalho > topo_continuacao:
                    bloco_continuacao = _BlocoPiloto(
                        numero_carro=piloto_atual[0],
                        nome=piloto_atual[1],
                        coluna=coluna,
                        top_inicio=topo_continuacao,
                        top_fim=topo_primeiro_cabecalho,
                    )
                    voltas = _extrair_voltas_do_bloco(
                        bloco_continuacao, linhas_logicas, posicoes_colunas, avisos
                    )
                    if voltas:
                        _obter_piloto(*piloto_atual).voltas.extend(voltas)

                # (2) Blocos com cabeçalho próprio nesta coluna.
                for bloco in blocos_coluna:
                    voltas = _extrair_voltas_do_bloco(
                        bloco, linhas_logicas, posicoes_colunas, avisos
                    )
                    piloto = _obter_piloto(bloco.numero_carro, bloco.nome)
                    if voltas:
                        piloto.voltas.extend(voltas)
                    # Esse piloto passa a ser o "em andamento" para a próxima
                    # coluna, mesmo que aqui ele não tenha tido voltas válidas.
                    piloto_atual = (bloco.numero_carro, bloco.nome)

    return ResultadoParsingPDF(
        arquivo_origem=caminho_pdf,
        pilotos=list(pilotos_por_chave.values()),
        avisos=avisos,
    )

"""
Cálculos de métricas a partir das voltas extraídas do PDF.

Todas as funções recebem objetos já extraídos (PilotoLaps / VoltaLeitura do
módulo parser) e devolvem modelos do app.models.metrics.

PRINCÍPIO QUE GUIA TUDO AQUI:
- Só calculamos com o que foi REALMENTE lido. Campos None (não lidos) são
  ignorados nos cálculos, e quando um resultado não pode ser produzido com
  confiança (ex: um setor sem nenhuma leitura), devolvemos None + um aviso.
  Nunca preenchemos com 0 ou estimativa.

DEFINIÇÕES (para os números terem significado claro):
- "Volta válida/limpa": volta que NÃO é de pit e que tem os TRÊS setores
  lidos (S1, S2 e S3). Exigir os três setores não é capricho: o cronômetro
  às vezes registra um "tempo de volta" sem ter medido um dos setores, e esse
  tempo sai implausivelmente curto (uma volta-fantasma). Confirmamos isso nos
  dados reais: tomar a "menor volta" sem esse filtro dava uma melhor volta
  mais rápida que a pole; já a "volta completa mais rápida" bate exatamente
  com o 'Best Tm' oficial do cronômetro para todos os 26 pilotos. É a base da
  melhor volta, da mediana e da consistência. (Não removemos outliers de
  tráfego além disso — seria um critério inventado; preferimos transparência.)
- "Melhor volta": menor tempo total entre as voltas válidas (acima).
- "Melhor volta teórica": soma do melhor S1 + melhor S2 + melhor S3 do piloto.
  Cada setor pode vir de uma volta diferente — e aqui usamos QUALQUER volta
  com aquele setor lido (mesmo que a volta não seja "completa"), porque um
  tempo de setor medido é válido por si só.
"""

import statistics
from typing import Optional

from app.models.lap_data import PilotoLaps, ResultadoParsingPDF
from app.models.metrics import (
    AnaliseSessao,
    ComparacaoSetor,
    DonoDoSetor,
    GapSetorPiloto,
    MetricasPiloto,
    VoltaIdealEquipe,
)

# Mapeia o número do setor (1,2,3) para o nome do atributo na VoltaLeitura.
_ATRIBUTO_SETOR = {1: "setor1_s", 2: "setor2_s", 3: "setor3_s"}


def _melhor_setor_do_piloto(piloto: PilotoLaps, setor: int) -> Optional[float]:
    """Menor tempo lido (não-None) do setor pedido, entre todas as voltas do piloto.

    Considera todas as voltas (inclusive pit): um tempo de setor válido é um
    tempo válido. Setores lentos de entrada/saída de box simplesmente não serão
    os menores, então não atrapalham. Devolve None se não houver leitura.
    """
    atributo = _ATRIBUTO_SETOR[setor]
    tempos = [
        getattr(v, atributo) for v in piloto.voltas if getattr(v, atributo) is not None
    ]
    return min(tempos) if tempos else None


def _voltas_validas(piloto: PilotoLaps):
    """
    Voltas "válidas/limpas": não são de pit e têm os TRÊS setores lidos.

    Exigir os três setores descarta as voltas-fantasma (tempo de volta sem um
    dos setores medido, que sai curto demais). Ver explicação no topo do
    arquivo. Como toda volta com os 3 setores também tem o tempo total, essas
    voltas servem tanto para a melhor volta quanto para mediana/consistência.
    """
    return [
        v
        for v in piloto.voltas
        if not v.eh_volta_pit
        and v.tempo_volta_s is not None
        and v.setor1_s is not None
        and v.setor2_s is not None
        and v.setor3_s is not None
    ]


def calcular_metricas_piloto(piloto: PilotoLaps) -> MetricasPiloto:
    """Calcula todas as métricas individuais de um piloto."""
    avisos: list[str] = []

    # Voltas válidas (não-pit, com os 3 setores). Base da melhor volta e das
    # estatísticas — ver _voltas_validas e o cabeçalho do arquivo.
    validas = _voltas_validas(piloto)
    tempos_validos = [v.tempo_volta_s for v in validas]

    # Melhor volta: menor tempo entre as voltas válidas. Guardamos também o
    # NÚMERO da volta em que ela ocorreu (equivale à coluna NA do oficial).
    if validas:
        volta_mais_rapida = min(validas, key=lambda v: v.tempo_volta_s)
        melhor_volta = volta_mais_rapida.tempo_volta_s
        numero_volta_melhor = volta_mais_rapida.numero_volta
    else:
        melhor_volta = None
        numero_volta_melhor = None
        avisos.append("Sem voltas válidas (não-pit, com os 3 setores) — sem melhor volta.")

    # Melhores setores do piloto.
    s1 = _melhor_setor_do_piloto(piloto, 1)
    s2 = _melhor_setor_do_piloto(piloto, 2)
    s3 = _melhor_setor_do_piloto(piloto, 3)

    # Volta teórica: só existe se os TRÊS setores têm leitura.
    if s1 is not None and s2 is not None and s3 is not None:
        teorica = s1 + s2 + s3
    else:
        teorica = None
        faltando = [str(n) for n, v in ((1, s1), (2, s2), (3, s3)) if v is None]
        avisos.append(
            f"Volta teórica não calculada: sem leitura válida no(s) setor(es) {', '.join(faltando)}."
        )

    # Gap real -> teórica.
    if melhor_volta is not None and teorica is not None:
        gap = melhor_volta - teorica
    else:
        gap = None

    # Estatísticas das voltas válidas (mesmo conjunto da melhor volta).
    mediana = statistics.median(tempos_validos) if tempos_validos else None
    if not tempos_validos:
        avisos.append("Sem voltas válidas — sem mediana.")
    # Desvio padrão amostral exige pelo menos 2 valores.
    if len(tempos_validos) >= 2:
        desvio = statistics.stdev(tempos_validos)
    else:
        desvio = None
        avisos.append("Menos de 2 voltas válidas — sem desvio padrão (consistência).")

    # SSTRAP (velocidade de radar) sobre voltas NÃO-pit com leitura: maior
    # valor = ponta; média = velocidade típica. Box laps ficam de fora.
    sstraps = [
        v.velocidade_radar_kmh
        for v in piloto.voltas
        if not v.eh_volta_pit and v.velocidade_radar_kmh is not None
    ]
    melhor_sstrap = max(sstraps) if sstraps else None
    sstrap_medio = statistics.mean(sstraps) if sstraps else None
    if not sstraps:
        avisos.append("Sem leitura de radar (SSTRAP) em voltas não-pit.")

    # Outliers de tráfego/bandeira: voltas válidas acima de mediana + 1,5x
    # desvio. Só sinalizamos (não apagamos): a mediana é robusta e quase não
    # sofre, mas o engenheiro precisa saber quais voltas "sujas" existem.
    voltas_outlier: list[int] = []
    if mediana is not None and desvio is not None:
        limite = mediana + 1.5 * desvio
        voltas_outlier = [v.numero_volta for v in validas if v.tempo_volta_s > limite]

    return MetricasPiloto(
        numero_carro=piloto.numero_carro,
        nome=piloto.nome,
        melhor_volta_s=melhor_volta,
        numero_volta_melhor=numero_volta_melhor,
        melhor_sstrap_kmh=melhor_sstrap,
        sstrap_medio_kmh=sstrap_medio,
        voltas_outlier=voltas_outlier,
        melhor_volta_teorica_s=teorica,
        gap_real_para_teorica_s=gap,
        mediana_voltas_limpas_s=mediana,
        consistencia_desvio_padrao_s=desvio,
        num_voltas_limpas=len(validas),
        melhor_setor1_s=s1,
        melhor_setor2_s=s2,
        melhor_setor3_s=s3,
        avisos=avisos,
    )


def calcular_volta_ideal_equipe(pilotos: list[PilotoLaps]) -> VoltaIdealEquipe:
    """
    Combina o melhor tempo de cada setor entre TODOS os pilotos.
    Para cada setor, guarda também de quem é o melhor tempo.
    """
    avisos: list[str] = []
    donos: dict[int, DonoDoSetor] = {}

    for setor in (1, 2, 3):
        melhor_tempo: Optional[float] = None
        dono: Optional[PilotoLaps] = None
        for piloto in pilotos:
            t = _melhor_setor_do_piloto(piloto, setor)
            if t is not None and (melhor_tempo is None or t < melhor_tempo):
                melhor_tempo = t
                dono = piloto
        if melhor_tempo is None:
            avisos.append(f"Setor {setor}: nenhum piloto tem leitura válida — não entra na volta ideal.")
            donos[setor] = DonoDoSetor(setor=setor)
        else:
            donos[setor] = DonoDoSetor(
                setor=setor,
                tempo_s=melhor_tempo,
                numero_carro_dono=dono.numero_carro,
                nome_dono=dono.nome,
            )

    tempos = [donos[s].tempo_s for s in (1, 2, 3)]
    total = sum(tempos) if all(t is not None for t in tempos) else None

    return VoltaIdealEquipe(
        setor1=donos[1],
        setor2=donos[2],
        setor3=donos[3],
        total_s=total,
        avisos=avisos,
    )


def comparar_setores(pilotos: list[PilotoLaps]) -> list[ComparacaoSetor]:
    """
    Para cada setor (1,2,3), compara o melhor tempo de cada piloto selecionado.
    O mais rápido vira a referência (gap 0); os demais recebem o gap em
    segundos e em % do tempo da referência.
    """
    comparacoes: list[ComparacaoSetor] = []

    for setor in (1, 2, 3):
        # Melhor tempo de setor de cada piloto (pode ser None).
        melhores = {
            p.numero_carro: (_melhor_setor_do_piloto(p, setor), p) for p in pilotos
        }
        # Referência = menor tempo válido entre os pilotos comparados.
        tempos_validos = [(t, p) for (t, p) in melhores.values() if t is not None]
        avisos: list[str] = []
        if not tempos_validos:
            avisos.append(f"Setor {setor}: nenhum dos pilotos selecionados tem leitura válida.")
            comparacoes.append(ComparacaoSetor(setor=setor, avisos=avisos))
            continue

        ref_tempo, ref_piloto = min(tempos_validos, key=lambda item: item[0])

        linhas: list[GapSetorPiloto] = []
        for piloto in pilotos:
            tempo, _ = melhores[piloto.numero_carro]
            if tempo is None:
                gap_s = None
                gap_pct = None
                avisos.append(
                    f"Setor {setor}: ({piloto.numero_carro}) {piloto.nome} sem leitura válida."
                )
            else:
                gap_s = tempo - ref_tempo
                gap_pct = (gap_s / ref_tempo) * 100 if ref_tempo else None
            linhas.append(
                GapSetorPiloto(
                    numero_carro=piloto.numero_carro,
                    nome=piloto.nome,
                    tempo_setor_s=tempo,
                    gap_para_referencia_s=gap_s,
                    gap_para_referencia_pct=gap_pct,
                )
            )

        comparacoes.append(
            ComparacaoSetor(
                setor=setor,
                referencia_numero_carro=ref_piloto.numero_carro,
                referencia_tempo_s=ref_tempo,
                pilotos=linhas,
                avisos=avisos,
            )
        )

    return comparacoes


def montar_analise_sessao(resultado: ResultadoParsingPDF) -> AnaliseSessao:
    """
    Junta tudo numa única resposta para o frontend: métricas de cada piloto,
    a volta ideal da equipe e a comparação setor a setor de TODO o grid (o
    frontend filtra os pilotos que quiser mostrar).
    """
    pilotos = resultado.pilotos
    return AnaliseSessao(
        arquivo_origem=resultado.arquivo_origem,
        num_pilotos=len(pilotos),
        pilotos=[calcular_metricas_piloto(p) for p in pilotos],
        volta_ideal_equipe=calcular_volta_ideal_equipe(pilotos),
        comparacao_setores=comparar_setores(pilotos),
        voltas_por_carro={p.numero_carro: p.voltas for p in pilotos},
        avisos_parsing=resultado.avisos,
    )

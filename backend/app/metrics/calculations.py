"""
Cálculos de métricas a partir das voltas extraídas do PDF.

Todas as funções recebem objetos já extraídos (PilotoLaps / VoltaLeitura do
módulo parser) e devolvem modelos do app.models.metrics.

PRINCÍPIO QUE GUIA TUDO AQUI:
- Só calculamos com o que foi REALMENTE lido. Campos None (não lidos) são
  ignorados nos cálculos, e quando um resultado não pode ser produzido com
  confiança (ex: um setor sem nenhuma leitura), devolvemos None + um aviso.
  Nunca preenchemos com 0 ou estimativa.

DEFINIÇÕES (validadas contra o cronômetro oficial em 36 relatórios Laptimes
de 5 categorias, Cuiabá e Cascavel):
- "Melhor volta OFICIAL": o próprio PDF imprime em NEGRITO a melhor volta de
  cada piloto. Esse negrito coincide com o 'Best Tm' do resumo oficial em
  866 de 866 carros — inclusive quando a direção de prova CANCELA voltas
  (ex.: limite de pista), algo que o Laptimes não mostra de outro jeito.
  Por isso, quando o relatório tem negrito, a melhor volta é a destacada.
- "Voltas desconsideradas": voltas completas MAIS RÁPIDAS que a melhor
  oficial. Se a cronometragem não as considerou, foram canceladas; ficam fora
  do ritmo e dos melhores setores, e aparecem listadas para o engenheiro.
- "Volta de saída de box": a volta 1 da sessão ou a seguinte a uma volta 'p'.
  O cronômetro não conta parte do tempo parado no box, então o total dessas
  voltas sai irreal. Ficam fora do ritmo, dos melhores setores e do radar.
- "Volta de ritmo": do tipo 'normal' (lançada, bandeira verde — ver
  tipos_volta.py: largada, box, Safety Car e relargada ficam de fora), não
  desconsiderada e com tempo total e TODOS os setores lidos (volta sem um
  setor medido pode ser uma "volta-fantasma" com tempo curto demais).
- "Melhor volta calculada" (só para relatórios SEM negrito): a volta completa
  fora do box mais rápida. Antes do negrito, foi essa a regra — acertava 835/866.
- "Melhor volta teórica": soma do melhor tempo de cada setor do piloto.

ESTATÍSTICAS PELA MEDIANA (e não pela média)
Numa sessão real sempre sobra uma volta com tráfego, bandeira ou erro. A
MÉDIA é puxada por ela; a MEDIANA (o tempo "do meio" da lista ordenada) não.
Pelo mesmo motivo a consistência usa o MAD — a mediana das distâncias de cada
volta até a mediana —, multiplicado por 1,4826 para ficar na mesma escala do
desvio padrão que o engenheiro conhece. Com menos de 4 voltas de ritmo os
números saem, mas marcados como "poucas voltas".
"""

import statistics
from typing import Optional

from app.metrics.tipos_volta import classificar_voltas
from app.models.lap_data import PilotoLaps, ResultadoParsingPDF, TipoVolta, VoltaLeitura
from app.models.metrics import (
    AnaliseSessao,
    ComparacaoSetor,
    DonoDoSetor,
    GapSetorPiloto,
    MetricasPiloto,
    RitmoTrecho,
    VoltaIdealEquipe,
)
from app.parser.tipo_pdf import TipoSessao

# Tolerância para comparar tempos (o cronômetro mede em milésimos).
_TOL = 0.0005
# Abaixo disso, mediana e consistência valem como indício ("poucas voltas").
MIN_VOLTAS_RITMO = 4
# Fator que põe o MAD na escala do desvio padrão (para dados sem outliers).
_FATOR_MAD = 1.4826
# Volta de ritmo mais lenta que mediana + 3 × consistência = provável tráfego.
_OUTLIER_SIGMAS = 3.0


def formatar_tempo(segundos: float) -> str:
    """77.319 -> '1:17.319' (formato de cronômetro, para os avisos)."""
    # Arredonda em milésimos ANTES de separar os minutos: senão 119.9996
    # viraria "1:60.000".
    minutos, milesimos = divmod(round(segundos * 1000), 60_000)
    resto = milesimos / 1000
    return f"{minutos}:{resto:06.3f}" if minutos else f"{resto:.3f}"


def _melhor_oficial(piloto: PilotoLaps) -> Optional[VoltaLeitura]:
    """A volta destacada em negrito (a primeira, em caso de empate de tempo)."""
    marcadas = [v for v in piloto.voltas if v.melhor_oficial and v.tempo_volta_s is not None]
    return min(marcadas, key=lambda v: (v.tempo_volta_s, v.numero_volta)) if marcadas else None


def _candidatas(piloto: PilotoLaps) -> list[VoltaLeitura]:
    """Voltas completas que não são de box (entrada nem saída)."""
    return [v for v in piloto.voltas if not v.eh_volta_pit and not v.eh_volta_saida_box and v.completa]


def _desconsideradas(piloto: PilotoLaps, usa_destaque: bool) -> set[int]:
    """Voltas completas mais rápidas que a melhor oficial (canceladas pela cronometragem)."""
    if not usa_destaque:
        return set()
    oficial = _melhor_oficial(piloto)
    if oficial is None:
        # Relatório com negrito, mas este piloto não tem melhor volta oficial:
        # nenhuma volta dele valeu para a cronometragem.
        return {v.numero_volta for v in _candidatas(piloto)}
    return {v.numero_volta for v in _candidatas(piloto) if v.tempo_volta_s < oficial.tempo_volta_s - _TOL}


def _voltas_ritmo(piloto: PilotoLaps, desconsideradas: set[int]) -> list[VoltaLeitura]:
    """Base do ritmo (mediana), da consistência e dos outliers: só voltas 'normal'."""
    return [
        v for v in _candidatas(piloto)
        if v.tipo is TipoVolta.NORMAL and v.numero_volta not in desconsideradas
    ]


def consistencia_mad(tempos: list[float]) -> Optional[float]:
    """Dispersão robusta: MAD × 1,4826. None com menos de 2 tempos."""
    if len(tempos) < 2:
        return None
    mediana = statistics.median(tempos)
    return round(_FATOR_MAD * statistics.median(abs(t - mediana) for t in tempos), 3)


def _ritmo_por_trecho(ritmo: list[VoltaLeitura]) -> list[RitmoTrecho]:
    por_trecho: dict[int, list[VoltaLeitura]] = {}
    for v in ritmo:
        if v.trecho is not None:
            por_trecho.setdefault(v.trecho, []).append(v)
    return [
        RitmoTrecho(
            trecho=t,
            voltas=[v.numero_volta for v in voltas],
            mediana_s=round(statistics.median(v.tempo_volta_s for v in voltas), 3),
            poucas_voltas=len(voltas) < MIN_VOLTAS_RITMO,
        )
        for t, voltas in sorted(por_trecho.items())
    ]


def _melhor_setor(piloto: PilotoLaps, indice: int, desconsideradas: set[int]) -> Optional[float]:
    """
    Menor tempo lido do setor `indice` (0 = S1). Ficam de fora a saída de box
    (split não confiável) e as voltas desconsideradas pela cronometragem. A
    volta de ENTRADA ('p') entra: os setores antes do box são medidos
    normalmente e o de entrada no box é lento — nunca será o mínimo.
    """
    tempos = [
        v.setores_s[indice]
        for v in piloto.voltas
        if indice < len(v.setores_s)
        and v.setores_s[indice] is not None
        and not v.eh_volta_saida_box
        and v.numero_volta not in desconsideradas
    ]
    return min(tempos) if tempos else None


def _usa_destaque(pilotos: list[PilotoLaps]) -> bool:
    """O relatório marca a melhor volta em negrito? (decide a regra da melhor volta)"""
    return any(v.melhor_oficial for p in pilotos for v in p.voltas)


def calcular_metricas_piloto(
    piloto: PilotoLaps, num_setores: int, usa_destaque: bool
) -> MetricasPiloto:
    """Calcula todas as métricas individuais de um piloto."""
    avisos: list[str] = []
    desconsideradas = _desconsideradas(piloto, usa_destaque)
    ritmo = _voltas_ritmo(piloto, desconsideradas)
    tempos_ritmo = [v.tempo_volta_s for v in ritmo]

    # --- Melhor volta ---
    origem = None
    if usa_destaque:
        oficial = _melhor_oficial(piloto)
        melhor_volta = oficial.tempo_volta_s if oficial else None
        numero_volta_melhor = oficial.numero_volta if oficial else None
        origem = "oficial" if oficial else None
        if oficial is None:
            avisos.append("Sem melhor volta oficial (nenhuma volta válida para a cronometragem).")
    elif candidatas := _candidatas(piloto):
        # Relatório sem negrito: a volta completa fora do box mais rápida
        # (largada e Safety Car nunca são as mais rápidas; relargada pode ser).
        v = min(candidatas, key=lambda v: v.tempo_volta_s)
        melhor_volta, numero_volta_melhor, origem = v.tempo_volta_s, v.numero_volta, "calculada"
    else:
        melhor_volta = numero_volta_melhor = None
        avisos.append("Sem voltas válidas (fora do box, com todos os setores) — sem melhor volta.")

    if desconsideradas and usa_destaque and melhor_volta is not None:
        tempos = {v.numero_volta: v.tempo_volta_s for v in piloto.voltas}
        lista = ", ".join(f"{n} ({formatar_tempo(tempos[n])})" for n in sorted(desconsideradas))
        plural = len(desconsideradas) > 1
        avisos.append(
            f"{'Voltas' if plural else 'Volta'} {lista} mais {'rápidas' if plural else 'rápida'} "
            f"que a melhor oficial ({formatar_tempo(melhor_volta)}): "
            f"{'desconsideradas' if plural else 'desconsiderada'} pela cronometragem (provável "
            f"cancelamento, ex.: limite de pista). Fora do ritmo e dos melhores setores."
        )

    # --- Setores e volta teórica ---
    setores = [_melhor_setor(piloto, i, desconsideradas) for i in range(num_setores)]
    if setores and all(s is not None for s in setores):
        teorica = round(sum(setores), 3)
    else:
        teorica = None
        faltando = [str(i + 1) for i, s in enumerate(setores) if s is None]
        avisos.append(
            f"Volta teórica não calculada: sem leitura válida no(s) setor(es) {', '.join(faltando)}."
        )
    gap = round(melhor_volta - teorica, 3) if melhor_volta is not None and teorica is not None else None

    # --- Ritmo e consistência (voltas de ritmo) ---
    mediana = round(statistics.median(tempos_ritmo), 3) if tempos_ritmo else None
    consistencia = consistencia_mad(tempos_ritmo)
    poucas = len(tempos_ritmo) < MIN_VOLTAS_RITMO
    # "Poucas voltas" não vira aviso: o campo poucas_voltas já marca isso na tela.
    if not tempos_ritmo:
        avisos.append("Sem voltas de ritmo (lançadas, fora do box e do Safety Car) — sem mediana.")

    # --- Radar: máximo fora do box; mediana nas voltas de ritmo ---
    radares = [
        v.velocidade_radar_kmh
        for v in piloto.voltas
        if not v.eh_volta_pit and not v.eh_volta_saida_box and v.velocidade_radar_kmh is not None
    ]
    radares_ritmo = [v.velocidade_radar_kmh for v in ritmo if v.velocidade_radar_kmh is not None]

    # --- Outliers de tráfego/bandeira (sinalizados, não removidos) ---
    voltas_outlier: list[int] = []
    if not poucas and consistencia:
        limite = mediana + _OUTLIER_SIGMAS * consistencia
        voltas_outlier = [v.numero_volta for v in ritmo if v.tempo_volta_s > limite]

    return MetricasPiloto(
        numero_carro=piloto.numero_carro,
        nome=piloto.nome,
        classe=piloto.classe,
        grupo=piloto.grupo,
        melhor_volta_s=melhor_volta,
        origem_melhor_volta=origem,
        numero_volta_melhor=numero_volta_melhor,
        voltas_desconsideradas=sorted(desconsideradas),
        melhor_volta_teorica_s=teorica,
        gap_real_para_teorica_s=gap,
        mediana_voltas_limpas_s=mediana,
        consistencia_s=consistencia,
        num_voltas_limpas=len(ritmo),
        poucas_voltas=poucas,
        ritmo_por_trecho=_ritmo_por_trecho(ritmo),
        melhores_setores_s=setores,
        radar_maximo_kmh=max(radares) if radares else None,
        radar_mediano_kmh=statistics.median(radares_ritmo) if radares_ritmo else None,
        voltas_outlier=voltas_outlier,
        avisos=avisos,
    )


def calcular_volta_ideal_equipe(
    pilotos: list[PilotoLaps], num_setores: int, usa_destaque: bool
) -> VoltaIdealEquipe:
    """Combina o melhor tempo de cada setor entre TODOS os pilotos (e de quem é)."""
    avisos: list[str] = []
    donos: list[DonoDoSetor] = []
    descons = {p.numero_carro: _desconsideradas(p, usa_destaque) for p in pilotos}

    for i in range(num_setores):
        melhor_tempo: Optional[float] = None
        dono: Optional[PilotoLaps] = None
        for piloto in pilotos:
            t = _melhor_setor(piloto, i, descons[piloto.numero_carro])
            if t is not None and (melhor_tempo is None or t < melhor_tempo):
                melhor_tempo, dono = t, piloto
        if melhor_tempo is None:
            avisos.append(f"Setor {i + 1}: nenhum piloto tem leitura válida — não entra na volta ideal.")
            donos.append(DonoDoSetor(setor=i + 1))
        else:
            donos.append(
                DonoDoSetor(
                    setor=i + 1, tempo_s=melhor_tempo,
                    numero_carro_dono=dono.numero_carro, nome_dono=dono.nome,
                    grupo_dono=dono.grupo,
                )
            )

    tempos = [d.tempo_s for d in donos]
    total = round(sum(tempos), 3) if tempos and all(t is not None for t in tempos) else None
    return VoltaIdealEquipe(setores=donos, total_s=total, avisos=avisos)


def comparar_setores(
    pilotos: list[PilotoLaps], num_setores: int, usa_destaque: bool
) -> list[ComparacaoSetor]:
    """
    Para cada setor, compara o melhor tempo de cada piloto. O mais rápido vira a
    referência (gap 0); os demais recebem o gap em segundos e em % da referência.
    """
    comparacoes: list[ComparacaoSetor] = []
    descons = {p.numero_carro: _desconsideradas(p, usa_destaque) for p in pilotos}

    for i in range(num_setores):
        setor = i + 1
        melhores = {p.numero_carro: _melhor_setor(p, i, descons[p.numero_carro]) for p in pilotos}
        validos = [(t, p) for p in pilotos if (t := melhores[p.numero_carro]) is not None]
        avisos: list[str] = []
        if not validos:
            avisos.append(f"Setor {setor}: nenhum dos pilotos tem leitura válida.")
            comparacoes.append(ComparacaoSetor(setor=setor, avisos=avisos))
            continue

        ref_tempo, ref_piloto = min(validos, key=lambda item: item[0])
        linhas: list[GapSetorPiloto] = []
        for piloto in pilotos:
            tempo = melhores[piloto.numero_carro]
            if tempo is None:
                gap_s = gap_pct = None
                avisos.append(f"Setor {setor}: ({piloto.numero_carro}) {piloto.nome} sem leitura válida.")
            else:
                gap_s = round(tempo - ref_tempo, 3)
                gap_pct = (gap_s / ref_tempo) * 100 if ref_tempo else None
            linhas.append(
                GapSetorPiloto(
                    numero_carro=piloto.numero_carro, nome=piloto.nome, tempo_setor_s=tempo,
                    gap_para_referencia_s=gap_s, gap_para_referencia_pct=gap_pct,
                )
            )
        comparacoes.append(
            ComparacaoSetor(
                setor=setor, referencia_numero_carro=ref_piloto.numero_carro,
                referencia_tempo_s=ref_tempo, pilotos=linhas, avisos=avisos,
            )
        )
    return comparacoes


def montar_analise_sessao(
    resultado: ResultadoParsingPDF,
    modo: TipoSessao = TipoSessao.TREINO,
    modo_detectado: Optional[TipoSessao] = None,
) -> AnaliseSessao:
    """
    Junta tudo numa única resposta para o frontend: métricas de cada piloto,
    a volta ideal da equipe e a comparação setor a setor de TODO o grid (o
    frontend filtra os pilotos que quiser mostrar).

    `modo` decide as regras (ver tipos_volta.py): na corrida, volta 1 é
    largada e os Safety Cars são detectados; no treino/qualy, os trechos são
    as saídas do box. Primeiro classificamos as voltas, depois calculamos.
    """
    pilotos = resultado.pilotos
    n = resultado.num_setores
    neutralizacoes = classificar_voltas(pilotos, n, modo)
    destaque = _usa_destaque(pilotos)
    return AnaliseSessao(
        arquivo_origem=resultado.arquivo_origem,
        num_pilotos=len(pilotos),
        num_setores=n,
        tem_radar=resultado.tem_radar,
        modo=modo.value,
        modo_detectado=modo_detectado.value if modo_detectado else None,
        neutralizacoes=neutralizacoes,
        pilotos=[calcular_metricas_piloto(p, n, destaque) for p in pilotos],
        volta_ideal_equipe=calcular_volta_ideal_equipe(pilotos, n, destaque),
        comparacao_setores=comparar_setores(pilotos, n, destaque),
        voltas_por_carro={p.numero_carro: p.voltas for p in pilotos},
        avisos_parsing=resultado.avisos,
    )

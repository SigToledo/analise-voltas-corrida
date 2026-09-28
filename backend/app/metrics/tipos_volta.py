"""
Classificação de cada volta: largada, box, Safety Car, relargada ou normal.

POR QUE ISSO IMPORTA
O ritmo de um piloto (mediana, consistência) só faz sentido com voltas em
bandeira verde. Voltas atrás do Safety Car vêm COMPLETAS no Laptimes (três
setores, sem nenhuma marca), então sem esta etapa elas entrariam no ritmo
como se o piloto tivesse andado 2 minutos por volta.

COMO O SAFETY CAR É DETECTADO (só no modo corrida)
O PDF não marca Safety Car. Mas ele tem uma assinatura clara: tráfego ou
um erro deixam UM piloto lento; o Safety Car deixa o GRID INTEIRO lento ao
mesmo tempo. Então:

1. Linha do tempo: somando as voltas de cada carro, sabemos em que momento
   da prova cada volta — e cada setor — começou e terminou. É o tempo, e não
   o número da volta, que alinha os carros: quando o líder está na volta 12,
   um retardatário ainda está na 11.
2. Cada setor é comparado com o melhor setor do PRÓPRIO piloto. Mais de 15%
   mais lento = "setor lento". (Volta sem os setores: compara a volta
   inteira, com 10%.) Largada e voltas de box ficam de fora da votação — o
   tempo delas é lento por outros motivos.
3. Em cada instante da prova, contamos quantos carros estão num setor lento.
   Quando são METADE ou mais, a corrida está neutralizada.
4. Buracos curtos dentro de um período (menos de 0,6 volta) são emendados, e
   períodos curtos demais (menos de 0,75 volta) são descartados: um Safety
   Car dura pelo menos uma volta.

Calibrado nas 7 corridas de Cascavel (MBR, Fórmula Truck, GT, Fusca, Speed
Max): acha todos os SCs visíveis nos tempos e nenhum na corrida limpa. Os
limites 10%/25% foram testados: 15% é o ponto estável.

A detecção é uma INFERÊNCIA e é apresentada como tal ("provável Safety Car",
com as voltas e o horário aproximado), nunca como dado do PDF.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Optional

from app.models.lap_data import PilotoLaps, TipoVolta, VoltaLeitura
from app.models.metrics import PeriodoNeutralizacao
from app.parser.tipo_pdf import TipoSessao

LIMIAR_SETOR = 1.15       # setor 15% mais lento que o melhor do piloto
LIMIAR_VOLTA = 1.10       # idem para a volta inteira, quando faltam setores
FRACAO_GRID = 0.5         # metade dos carros na pista
MIN_CARROS = 3            # com menos carros rodando, não há "grid" para votar
EMENDA_VOLTAS = 0.6       # buraco menor que isso (em voltas) é emendado
DURACAO_MIN_VOLTAS = 0.75 # período menor que isso (em voltas) é descartado
_FOLGA_SOMA_SETORES = 0.5 # segundos: setores que não somam o total não são usados


@dataclass
class _Segmento:
    """Um pedaço da linha do tempo de um carro (um setor ou uma volta inteira)."""

    inicio: float
    fim: float
    lento: Optional[bool]  # None = não entra na votação (largada, box)


def linha_do_tempo(piloto: PilotoLaps) -> list[tuple[VoltaLeitura, float, float]]:
    """
    (volta, início, fim) em segundos de prova, somando os tempos de volta.
    Para na primeira volta sem tempo: depois dela não sabemos mais onde o
    carro estava — e não chutamos.
    """
    t = 0.0
    saida = []
    for v in piloto.voltas:
        if v.tempo_volta_s is None:
            break
        saida.append((v, t, t + v.tempo_volta_s))
        t += v.tempo_volta_s
    return saida


def _fora_da_votacao(v: VoltaLeitura) -> bool:
    return v.numero_volta == 1 or v.eh_volta_pit or v.eh_volta_saida_box


def _referencias(piloto: PilotoLaps, num_setores: int) -> tuple[list[Optional[float]], Optional[float]]:
    """Melhor tempo de cada setor e da volta do piloto, fora largada/box."""
    voltas = [v for v in piloto.voltas if not _fora_da_votacao(v)]
    setores = []
    for i in range(num_setores):
        tempos = [v.setores_s[i] for v in voltas if i < len(v.setores_s) and v.setores_s[i] is not None]
        setores.append(min(tempos) if tempos else None)
    tempos_volta = [v.tempo_volta_s for v in voltas if v.tempo_volta_s is not None]
    return setores, (min(tempos_volta) if tempos_volta else None)


def _setores_confiaveis(v: VoltaLeitura) -> bool:
    return v.completa and bool(v.setores_s) and abs(sum(v.setores_s) - v.tempo_volta_s) <= _FOLGA_SOMA_SETORES


def _segmentos_da_volta(
    v: VoltaLeitura, inicio: float, fim: float, ref_setores: list[Optional[float]], ref_volta: Optional[float]
) -> list[_Segmento]:
    fora = _fora_da_votacao(v)
    if _setores_confiaveis(v):
        segs, t = [], inicio
        for i, s in enumerate(v.setores_s):
            ref = ref_setores[i] if i < len(ref_setores) else None
            segs.append(_Segmento(t, t + s, None if fora or ref is None else s > LIMIAR_SETOR * ref))
            t += s
        return segs
    lento = None if fora or ref_volta is None else v.tempo_volta_s > LIMIAR_VOLTA * ref_volta
    return [_Segmento(inicio, fim, lento)]


def _volta_tipica(pilotos: list[PilotoLaps]) -> Optional[float]:
    """Mediana das melhores voltas do grid: a 'régua' para durações."""
    melhores = [r for p in pilotos if (r := _referencias(p, 0)[1]) is not None]
    return statistics.median(melhores) if melhores else None


def detectar_neutralizacoes(pilotos: list[PilotoLaps], num_setores: int) -> list[tuple[float, float]]:
    """Intervalos (início, fim), em segundos de prova, em que o grid ficou lento junto."""
    volta_tipica = _volta_tipica(pilotos)
    if volta_tipica is None:
        return []

    # Varredura: cada segmento conhecido soma 1 carro "rodando" no início e
    # tira no fim; se for lento, idem na contagem de lentos.
    eventos: list[tuple[float, int, int]] = []
    for p in pilotos:
        ref_setores, ref_volta = _referencias(p, num_setores)
        for v, ini, fim in linha_do_tempo(p):
            for seg in _segmentos_da_volta(v, ini, fim, ref_setores, ref_volta):
                if seg.lento is None or seg.fim <= seg.inicio:
                    continue
                eventos.append((seg.inicio, 1, int(seg.lento)))
                eventos.append((seg.fim, -1, -int(seg.lento)))
    eventos.sort()

    brutos: list[list[float]] = []
    rodando = lentos = 0
    for i, (t, d_rodando, d_lentos) in enumerate(eventos):
        rodando += d_rodando
        lentos += d_lentos
        proximo = eventos[i + 1][0] if i + 1 < len(eventos) else t
        if proximo <= t:
            continue
        if rodando >= MIN_CARROS and lentos >= FRACAO_GRID * rodando:
            if brutos and t - brutos[-1][1] <= 1e-6:
                brutos[-1][1] = proximo
            else:
                brutos.append([t, proximo])

    emendados: list[list[float]] = []
    for ini, fim in brutos:
        if emendados and ini - emendados[-1][1] < EMENDA_VOLTAS * volta_tipica:
            emendados[-1][1] = fim
        else:
            emendados.append([ini, fim])
    return [(ini, fim) for ini, fim in emendados if fim - ini >= DURACAO_MIN_VOLTAS * volta_tipica]


def _volta_lenta(v: VoltaLeitura, ini: float, fim: float, ref_setores, ref_volta) -> bool:
    return any(s.lento for s in _segmentos_da_volta(v, ini, fim, ref_setores, ref_volta))


def _marcar_neutralizacoes(
    pilotos: list[PilotoLaps], num_setores: int, periodos: list[tuple[float, float]]
) -> None:
    """
    Volta de Safety Car = cruza um período E (tem setor lento OU passa mais
    da metade dentro dele). O "E" evita marcar a volta da relargada, que
    começa segundos antes do fim oficial do período mas já é lançada.
    """
    for p in pilotos:
        ref_setores, ref_volta = _referencias(p, num_setores)
        for v, ini, fim in linha_do_tempo(p):
            for k, (a, b) in enumerate(periodos, start=1):
                dentro = min(fim, b) - max(ini, a)
                if dentro <= 0:
                    continue
                if dentro >= 0.5 * (fim - ini) or _volta_lenta(v, ini, fim, ref_setores, ref_volta):
                    v.neutralizacao = k
                    break
            if v.neutralizacao is None:
                meio = (ini + fim) / 2
                v.trecho = 1 + sum(1 for _, b in periodos if b <= meio)


def _lider(pilotos: list[PilotoLaps]) -> Optional[PilotoLaps]:
    """Quem completou mais voltas (desempate: menor tempo somado)."""
    if not pilotos:
        return None
    return max(pilotos, key=lambda p: (len(p.voltas), -sum(v.tempo_volta_s or 0.0 for v in p.voltas)))


def classificar_voltas(
    pilotos: list[PilotoLaps], num_setores: int, modo: TipoSessao
) -> list[PeriodoNeutralizacao]:
    """
    Preenche `tipo`, `neutralizacao` e `trecho` de cada volta conforme o modo
    e devolve os prováveis Safety Cars (vazio fora do modo corrida).
    """
    for p in pilotos:
        for v in p.voltas:
            v.tipo, v.neutralizacao, v.trecho = TipoVolta.NORMAL, None, None

    corrida = modo is TipoSessao.CORRIDA
    periodos = detectar_neutralizacoes(pilotos, num_setores) if corrida else []
    if corrida:
        _marcar_neutralizacoes(pilotos, num_setores, periodos)

    for p in pilotos:
        saida_atual = 0
        anterior: Optional[VoltaLeitura] = None
        for v in p.voltas:
            if not corrida:
                # Treino/qualy: cada saída do box abre um trecho novo (a volta
                # 'p' fecha o trecho em que o carro estava).
                if v.eh_volta_saida_box or saida_atual == 0:
                    saida_atual += 1
                v.trecho = saida_atual

            if v.eh_volta_pit:
                v.tipo = TipoVolta.ENTRADA_BOX
            elif corrida and v.numero_volta == 1:
                v.tipo = TipoVolta.LARGADA
            elif v.eh_volta_saida_box:
                v.tipo = TipoVolta.SAIDA_BOX
            elif v.neutralizacao is not None:
                v.tipo = TipoVolta.SAFETY_CAR
            elif anterior is not None and anterior.neutralizacao is not None:
                v.tipo = TipoVolta.RELARGADA
            anterior = v

    lider = _lider(pilotos)
    saida: list[PeriodoNeutralizacao] = []
    for k, (a, b) in enumerate(periodos, start=1):
        voltas_lider = [v.numero_volta for v in lider.voltas if v.neutralizacao == k] if lider else []
        saida.append(
            PeriodoNeutralizacao(
                numero=k, inicio_s=round(a, 1), fim_s=round(b, 1),
                volta_inicial_lider=min(voltas_lider) if voltas_lider else None,
                volta_final_lider=max(voltas_lider) if voltas_lider else None,
            )
        )
    return saida

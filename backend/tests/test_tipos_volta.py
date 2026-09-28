"""
Testes da classificação de voltas (largada, box, Safety Car, relargada) e
dos trechos.

- Casos sintéticos: grid pequeno montado à mão, para cada regra isolada.
- Corridas reais de Cascavel (em samples/, fora do Git): os Safety Cars
  esperados foram conferidos na matriz de tempos de cada corrida — o grid
  inteiro fica lento nas mesmas voltas. Sem os PDFs, esses testes são pulados.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.metrics.calculations import montar_analise_sessao
from app.metrics.tipos_volta import classificar_voltas
from app.models.lap_data import PilotoLaps, ResultadoParsingPDF, TipoVolta, VoltaLeitura
from app.parser.laptimes_parser import parse_laptimes_pdf
from app.parser.tipo_pdf import TipoSessao

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def _volta(n: int, s1: float, s2: float, s3: float, pit: bool = False) -> VoltaLeitura:
    return VoltaLeitura(
        numero_volta=n, eh_volta_pit=pit, eh_volta_saida_box=False,
        tempo_volta_s=round(s1 + s2 + s3, 3), setores_s=[s1, s2, s3],
    )


def _piloto(carro: str, voltas: list[VoltaLeitura]) -> PilotoLaps:
    pits = {v.numero_volta for v in voltas if v.eh_volta_pit}
    for v in voltas:
        v.eh_volta_saida_box = v.numero_volta == 1 or (v.numero_volta - 1) in pits
    return PilotoLaps(numero_carro=carro, nome=f"P{carro}", voltas=voltas)


def _corrida_com_sc(num_carros: int = 6) -> list[PilotoLaps]:
    """Voltas de 60 s (20+25+15); voltas 4 e 5 atrás do SC (90 s)."""
    pilotos = []
    for c in range(num_carros):
        extra = c * 0.1  # carros um pouco diferentes entre si
        voltas = []
        for n in range(1, 9):
            if n in (4, 5):
                voltas.append(_volta(n, 30 + extra, 37.5, 22.5))
            else:
                voltas.append(_volta(n, 20 + extra, 25, 15))
        pilotos.append(_piloto(str(c + 1), voltas))
    return pilotos


def _tipos(p: PilotoLaps) -> str:
    letra = {
        TipoVolta.NORMAL: ".", TipoVolta.LARGADA: "L", TipoVolta.SAIDA_BOX: "S",
        TipoVolta.ENTRADA_BOX: "P", TipoVolta.SAFETY_CAR: "C", TipoVolta.RELARGADA: "R",
    }
    return "".join(letra[v.tipo] for v in p.voltas)


def test_safety_car_do_grid_inteiro_e_detectado():
    pilotos = _corrida_com_sc()
    periodos = classificar_voltas(pilotos, 3, TipoSessao.CORRIDA)
    assert len(periodos) == 1
    assert (periodos[0].volta_inicial_lider, periodos[0].volta_final_lider) == (4, 5)
    # Largada, 2 lançadas, SC, SC, relargada, 2 lançadas.
    assert all(_tipos(p) == "L..CCR.." for p in pilotos)
    # Trechos de bandeira verde: 1 antes do SC, 2 depois (SC fica sem trecho).
    assert [v.trecho for v in pilotos[0].voltas] == [1, 1, 1, None, None, 2, 2, 2]


def test_um_piloto_lento_sozinho_nao_e_safety_car():
    """Tráfego/erro afeta UM piloto: não pode virar neutralização."""
    pilotos = []
    for c in range(6):
        voltas = [_volta(n, 20, 25, 15) for n in range(1, 9)]
        if c == 0:
            voltas[3] = _volta(4, 30, 37.5, 22.5)
            voltas[4] = _volta(5, 30, 37.5, 22.5)
        pilotos.append(_piloto(str(c + 1), voltas))
    assert classificar_voltas(pilotos, 3, TipoSessao.CORRIDA) == []
    assert _tipos(pilotos[0]) == "L......."


def test_treino_nao_detecta_safety_car_e_trecho_e_a_saida_do_box():
    """No treino, o tempo parado no box não é contado, então a soma das
    voltas não é o relógio da sessão: não há detecção de SC. Cada saída do
    box abre um trecho novo."""
    pilotos = _corrida_com_sc()
    pilotos[0] = _piloto(
        "1", [_volta(1, 20, 25, 15), _volta(2, 20, 25, 15), _volta(3, 20, 25, 30, pit=True),
              _volta(4, 20, 25, 15), _volta(5, 20, 25, 15)],
    )
    assert classificar_voltas(pilotos, 3, TipoSessao.TREINO) == []
    assert _tipos(pilotos[0]) == "S.PS."
    assert [v.trecho for v in pilotos[0].voltas] == [1, 1, 1, 2, 2]
    assert _tipos(pilotos[1]) == "S......."  # SC do grid ignorado no treino


def test_mediana_do_piloto_ignora_voltas_de_safety_car():
    analise = montar_analise_sessao(
        ResultadoParsingPDF(arquivo_origem="x.pdf", num_setores=3, pilotos=_corrida_com_sc()),
        TipoSessao.CORRIDA,
    )
    p = analise.pilotos[0]
    # Voltas de ritmo: 2, 3, 7, 8 (60 s cada). Largada, SC e relargada fora.
    assert p.num_voltas_limpas == 4
    assert p.mediana_voltas_limpas_s == pytest.approx(60.0)
    assert p.consistencia_s == pytest.approx(0.0)
    assert [(t.trecho, t.voltas) for t in p.ritmo_por_trecho] == [(1, [2, 3]), (2, [7, 8])]
    assert all(t.poucas_voltas for t in p.ritmo_por_trecho)
    assert analise.modo == "corrida"
    assert len(analise.neutralizacoes) == 1


# Safety Cars conferidos na matriz de tempos (voltas do líder).
SC_ESPERADOS = {
    "5ET - MBR - CASCAVEL/SABADO/5ET - MBR - CORRIDA 1 - MBR - Laptimes_sec4.pdf":
        [(2, 4), (10, 13), (19, 21)],
    "5ET - MBR - CASCAVEL/DOMINGO/5ET - MBR - CORRIDA 2 - MBR - Laptimes_sec4.pdf":
        [(2, 4), (11, 12), (14, 15), (18, 20)],
    "7ET - CASCAVEL/7ET - SPEEDMAX - CORRIDA TROFEU SPEED MAX - Laptimes_sec4.pdf":
        [(11, 13)],
    "7ET - CASCAVEL/FORMULA FUSCA BR - CASCAVEL/FORMULA FUSCA BR - CORRIDA 1 - FUSCA - Laptimes_sec4.pdf":
        [],
    "7ET - CASCAVEL/FORMULA FUSCA BR - CASCAVEL/FORMULA FUSCA BR - CORRIDA 2 - FUSCA - Laptimes_sec4.pdf":
        [(8, 9), (12, 13)],
    "7ET - CASCAVEL/FT/7ET - FT - BOMBA INJETORA - CORRIDA - FT - Laptimes_sec4.pdf":
        [(2, 2), (9, 10), (22, 23)],
    "7ET - CASCAVEL/GT/7ET - GT - ELETRONICO - CORRIDA - GT - Laptimes_sec4.pdf":
        [(2, 4), (16, 18)],
}


@pytest.mark.parametrize("relativo", sorted(SC_ESPERADOS))
def test_safety_cars_das_corridas_de_cascavel(relativo):
    caminho = SAMPLES / relativo
    if not caminho.exists():
        pytest.skip(f"PDF real não encontrado: {relativo}")
    r = parse_laptimes_pdf(str(caminho))
    periodos = classificar_voltas(r.pilotos, r.num_setores, TipoSessao.CORRIDA)
    assert [(p.volta_inicial_lider, p.volta_final_lider) for p in periodos] == SC_ESPERADOS[relativo]


# Voltas lentas de UM carro só (incidente individual), fora de qualquer SC.
INCIDENTES_INDIVIDUAIS = [
    ("7ET - CASCAVEL/FORMULA FUSCA BR - CASCAVEL/FORMULA FUSCA BR - CORRIDA 1 - FUSCA - Laptimes_sec4.pdf", "77", 19),
    ("7ET - CASCAVEL/FT/7ET - FT - BOMBA INJETORA - CORRIDA - FT - Laptimes_sec4.pdf", "600", 15),
    ("7ET - CASCAVEL/GT/7ET - GT - ELETRONICO - CORRIDA - GT - Laptimes_sec4.pdf", "51", 11),
]


@pytest.mark.parametrize("relativo,carro,volta", INCIDENTES_INDIVIDUAIS)
def test_incidente_de_um_carro_nao_vira_safety_car(relativo, carro, volta):
    """Voltas 30% ou mais lentas que a melhor do piloto, mas SÓ dele: continuam
    'normal' (e a mediana/MAD cuidam delas como outlier)."""
    caminho = SAMPLES / relativo
    if not caminho.exists():
        pytest.skip(f"PDF real não encontrado: {relativo}")
    r = parse_laptimes_pdf(str(caminho))
    analise = montar_analise_sessao(r, TipoSessao.CORRIDA)
    v = next(v for v in analise.voltas_por_carro[carro] if v.numero_volta == volta)
    assert v.tipo is TipoVolta.NORMAL and v.neutralizacao is None
    metricas = next(p for p in analise.pilotos if p.numero_carro == carro)
    assert volta in metricas.voltas_outlier


def test_safety_car_obrigatorio_da_mbr_aos_15_minutos():
    """Regulamento da MBR (corridas 1 e 2): SC obrigatório aos 15 min. O
    detector não sabe disso — mas deve achá-lo pelos dados."""
    for relativo in list(SC_ESPERADOS)[:2]:
        caminho = SAMPLES / relativo
        if not caminho.exists():
            pytest.skip(f"PDF real não encontrado: {relativo}")
        r = parse_laptimes_pdf(str(caminho))
        periodos = classificar_voltas(r.pilotos, r.num_setores, TipoSessao.CORRIDA)
        assert any(14 * 60 <= p.inicio_s <= 17 * 60 for p in periodos), relativo


def test_api_modo_automatico_e_escolhido():
    caminho = SAMPLES / list(SC_ESPERADOS)[0]
    if not caminho.exists():
        pytest.skip("PDF real não encontrado")
    client = TestClient(app)
    with caminho.open("rb") as f:
        conteudo = f.read()
    auto = client.post("/analise", files={"arquivo": (caminho.name, conteudo, "application/pdf")}).json()
    assert auto["modo"] == auto["modo_detectado"] == "corrida"
    assert len(auto["neutralizacoes"]) == 3
    assert auto["voltas_por_carro"]["77"][0]["tipo"] == "largada"

    treino = client.post(
        "/analise", files={"arquivo": (caminho.name, conteudo, "application/pdf")}, data={"modo": "treino"}
    ).json()
    assert treino["modo"] == "treino" and treino["modo_detectado"] == "corrida"
    assert treino["neutralizacoes"] == []
    assert treino["voltas_por_carro"]["77"][0]["tipo"] == "saida_box"

    ruim = client.post(
        "/analise", files={"arquivo": (caminho.name, conteudo, "application/pdf")}, data={"modo": "sprint"}
    )
    assert ruim.status_code == 400

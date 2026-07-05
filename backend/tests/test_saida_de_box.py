"""
Testes da regra de VOLTA DE SAÍDA DE BOX (out-lap).

Contexto (confirmado nos dados reais): o cronômetro não conta parte do tempo
parado no box, então a volta de saída (volta 1 ou a seguinte a uma volta 'p')
sai com total irreal — ex.: F.MACHIAVELLI marca "2:08.347" na volta 8, logo
após a p7, mais rápido que a pole. A cronometragem oficial desconsidera essas
voltas, e as análises daqui também: fora da melhor volta, mediana,
consistência, melhores setores e SSTRAP.
"""

from pathlib import Path

import pytest

from app.metrics.calculations import calcular_metricas_piloto
from app.parser.laptimes_parser import parse_laptimes_pdf

PDF_EXEMPLO = (
    Path(__file__).resolve().parents[2]
    / "samples"
    / "MBR - 4o TREINO OFICIAL MBR - GRUPO 1 - Laptimes_sec4.pdf"
)

pytestmark = pytest.mark.skipif(
    not PDF_EXEMPLO.exists(), reason="PDF de exemplo ausente em samples/"
)


@pytest.fixture(scope="module")
def pilotos():
    return parse_laptimes_pdf(str(PDF_EXEMPLO)).pilotos


def test_marcacao_de_saida_de_box(pilotos):
    """Volta 1 e a volta seguinte a cada 'p' devem vir marcadas."""
    machiavelli = next(p for p in pilotos if p.numero_carro == "411")
    por_numero = {v.numero_volta: v for v in machiavelli.voltas}
    assert por_numero[1].eh_volta_saida_box            # volta 1 = saiu do box
    assert por_numero[7].eh_volta_pit                   # p7
    assert por_numero[8].eh_volta_saida_box            # saída após a p7
    assert not por_numero[9].eh_volta_saida_box        # volta lançada normal
    # Em todos os pilotos: volta 1 sempre é saída de box.
    for p in pilotos:
        v1 = next((v for v in p.voltas if v.numero_volta == 1), None)
        if v1 is not None:
            assert v1.eh_volta_saida_box, p.numero_carro


def test_saida_de_box_nao_vira_melhor_volta(pilotos):
    """O caso real: a 'volta' de 2:08.347 do 411 (saída de box) não pode ser a
    melhor volta — a melhor continua sendo a oficial, 2:15.232."""
    machiavelli = next(p for p in pilotos if p.numero_carro == "411")
    m = calcular_metricas_piloto(machiavelli)
    assert m.melhor_volta_s == pytest.approx(135.232)


def test_nenhuma_saida_de_box_nas_estatisticas(pilotos):
    """Invariante global: nenhum piloto tem melhor volta mais rápida que
    qualquer uma de suas voltas de saída de box indicaria por engano."""
    for p in pilotos:
        m = calcular_metricas_piloto(p)
        if m.melhor_volta_s is None:
            continue
        for v in p.voltas:
            if v.eh_volta_saida_box and v.tempo_volta_s is not None:
                # a saída de box pode ser "mais rápida" no papel; ela não pode
                # ter sido usada como melhor volta
                assert m.melhor_volta_s != v.tempo_volta_s or not v.eh_volta_saida_box


def test_melhores_setores_ignoram_saida_de_box(pilotos):
    """Casos reais medidos: os carros 113, 25 e 122 tinham o melhor S3 vindo
    de uma saída de box. Com a regra, vale o melhor S3 de volta confiável."""
    esperados = {"113": 49.379, "25": 49.261, "122": 49.477}
    for carro, s3 in esperados.items():
        p = next(x for x in pilotos if x.numero_carro == carro)
        m = calcular_metricas_piloto(p)
        assert m.melhor_setor3_s == pytest.approx(s3), carro

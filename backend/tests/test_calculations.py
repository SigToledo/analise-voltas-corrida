"""
Testes dos cálculos de métricas, rodando sobre o PDF real de exemplo.

Estratégia de validação (para não ser circular, isto é, não usar o próprio
código como única fonte de verdade):
- A MELHOR VOLTA de cada piloto é checada contra a coluna "Best Tm" da
  tabela QualifyReduced (uma fonte independente, gerada pelo cronômetro).
- Alguns valores de L.JOSE (171) foram conferidos à mão no PDF.
- O resto usa invariantes que sempre têm de valer (ex: volta teórica <=
  melhor volta real).
"""

from pathlib import Path

import pytest

from app.metrics.calculations import (
    calcular_metricas_piloto,
    calcular_volta_ideal_equipe,
    comparar_setores,
)
from app.parser.laptimes_parser import parse_laptimes_pdf

PDF_EXEMPLO = (
    Path(__file__).resolve().parents[2]
    / "samples"
    / "MBR - 4o TREINO OFICIAL MBR - GRUPO 1 - Laptimes_sec4.pdf"
)

# "Best Tm" oficial (QualifyReduced), em texto M:SS.mmm, por número de carro.
MELHOR_VOLTA_OFICIAL_TXT = {
    "171": "2:14.353", "411": "2:15.232", "197": "2:16.197", "82": "2:16.264",
    "98": "2:16.435", "899": "2:16.542", "11": "2:16.967", "96": "2:17.291",
    "15": "2:17.385", "4": "2:17.575", "47": "2:17.589", "500": "2:18.011",
    "19": "2:18.096", "113": "2:18.375", "91": "2:18.465", "328": "2:18.496",
    "225": "2:18.567", "707": "2:19.845", "25": "2:20.568", "66": "2:20.622",
    "122": "2:20.828", "38": "2:21.421", "18": "2:21.702", "422": "2:24.684",
    "55": "2:25.554", "8": "2:26.902",
}


def _para_segundos(txt: str) -> float:
    minutos, resto = txt.split(":")
    return int(minutos) * 60 + float(resto)


@pytest.fixture(scope="module")
def pilotos():
    if not PDF_EXEMPLO.exists():
        pytest.skip(f"PDF de exemplo não encontrado em {PDF_EXEMPLO}")
    return parse_laptimes_pdf(str(PDF_EXEMPLO)).pilotos


def test_melhor_volta_bate_com_a_oficial(pilotos):
    """A melhor volta calculada deve bater com o 'Best Tm' oficial, para todos."""
    por_carro = {p.numero_carro: p for p in pilotos}
    for carro, txt in MELHOR_VOLTA_OFICIAL_TXT.items():
        m = calcular_metricas_piloto(por_carro[carro], 3, True)
        assert m.melhor_volta_s == pytest.approx(_para_segundos(txt)), carro


def test_volta_teorica_nunca_maior_que_a_real(pilotos):
    """Invariante: a volta teórica (melhores setores) nunca é mais lenta que a
    melhor volta real, porque os setores da melhor volta são candidatos."""
    for p in pilotos:
        m = calcular_metricas_piloto(p, 3, True)
        if m.melhor_volta_s is not None and m.melhor_volta_teorica_s is not None:
            assert m.melhor_volta_teorica_s <= m.melhor_volta_s + 1e-9, p.numero_carro


def test_metricas_ljose_conferidas_a_mao(pilotos):
    """L.JOSE (171): valores conferidos diretamente no PDF.

    Melhores setores: S1 36.711, S2 49.980, S3 47.662 (todos na volta 10).
    Logo a teórica = 134.353 = a própria melhor volta, e o gap = 0.
    """
    ljose = next(p for p in pilotos if p.numero_carro == "171")
    m = calcular_metricas_piloto(ljose, 3, True)
    assert m.melhores_setores_s[0] == pytest.approx(36.711)
    assert m.melhores_setores_s[1] == pytest.approx(49.980)
    assert m.melhores_setores_s[2] == pytest.approx(47.662)
    assert m.melhor_volta_teorica_s == pytest.approx(134.353)
    assert m.melhor_volta_s == pytest.approx(134.353)
    assert m.gap_real_para_teorica_s == pytest.approx(0.0, abs=1e-6)


def test_voltas_validas_excluem_pit_e_incompletas(pilotos):
    """Voltas válidas de L.JOSE = não-pit COM os 3 setores.

    Das 10 voltas: v5 e v8 são pit; v1, v6 e v9 não têm S1. Sobram 5 válidas
    (v2, v3, v4, v7, v10)."""
    ljose = next(p for p in pilotos if p.numero_carro == "171")
    m = calcular_metricas_piloto(ljose, 3, True)
    assert m.num_voltas_limpas == 5
    assert m.consistencia_desvio_padrao_s is not None  # >= 2 voltas válidas
    assert m.mediana_voltas_limpas_s is not None


# Coluna "NA" do QualifyReduced = número da volta da melhor marca.
NA_OFICIAL = {
    "171": 10, "411": 9, "197": 3, "82": 10, "98": 9, "899": 3, "11": 3,
    "96": 10, "15": 4, "4": 4, "47": 6, "500": 3, "19": 3, "113": 7, "91": 10,
    "328": 7, "225": 10, "707": 7, "25": 3, "66": 3, "122": 6, "38": 7,
    "18": 3, "422": 8, "55": 9, "8": 2,
}


def test_numero_da_melhor_volta_bate_com_NA(pilotos):
    """O número da volta da melhor marca deve bater com a coluna NA oficial."""
    por_carro = {p.numero_carro: p for p in pilotos}
    for carro, na in NA_OFICIAL.items():
        m = calcular_metricas_piloto(por_carro[carro], 3, True)
        assert m.numero_volta_melhor == na, carro


def test_sstrap_e_outliers_ljose(pilotos):
    """SSTRAP de L.JOSE: melhor 184.3 km/h (volta 4). A volta 2 (com tráfego)
    deve ser sinalizada como outlier, sem ser removida da contagem de válidas."""
    ljose = next(p for p in pilotos if p.numero_carro == "171")
    m = calcular_metricas_piloto(ljose, 3, True)
    assert m.melhor_sstrap_kmh == pytest.approx(184.3)
    assert m.sstrap_medio_kmh is not None
    assert 2 in m.voltas_outlier
    assert m.num_voltas_limpas == 5  # outlier sinalizado, não removido


def test_volta_ideal_equipe(pilotos):
    """A volta ideal soma os melhores setores do grid todo e deve ser <= a
    melhor volta do piloto mais rápido da sessão."""
    ideal = calcular_volta_ideal_equipe(pilotos, 3, True)
    assert ideal.total_s is not None
    # Cada setor tem dono identificado.
    for setor in ideal.setores:
        assert setor.tempo_s is not None
        assert setor.numero_carro_dono is not None
    # total = soma dos três setores.
    assert ideal.total_s == pytest.approx(
        sum(s.tempo_s for s in ideal.setores)
    )
    # A melhor volta do grid é 2:14.353 (171). A ideal não pode ser mais lenta.
    assert ideal.total_s <= _para_segundos("2:14.353") + 1e-9


def test_comparar_setores_referencia_tem_gap_zero(pilotos):
    """Na comparação, o piloto de referência (mais rápido no setor) tem gap 0,
    e os demais têm gap positivo em segundos e %."""
    por_carro = {p.numero_carro: p for p in pilotos}
    selecionados = [por_carro["171"], por_carro["411"], por_carro["197"]]
    comparacoes = comparar_setores(selecionados, 3, True)
    assert len(comparacoes) == 3
    for comp in comparacoes:
        ref = comp.referencia_numero_carro
        assert ref is not None
        for linha in comp.pilotos:
            if linha.numero_carro == ref:
                assert linha.gap_para_referencia_s == pytest.approx(0.0, abs=1e-9)
                assert linha.gap_para_referencia_pct == pytest.approx(0.0, abs=1e-9)
            elif linha.tempo_setor_s is not None:
                assert linha.gap_para_referencia_s > 0
                assert linha.gap_para_referencia_pct > 0

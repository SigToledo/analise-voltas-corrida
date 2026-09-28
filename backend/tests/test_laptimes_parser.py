"""
Teste do parser contra o PDF REAL de exemplo (samples/Laptimes_sec4.pdf).

Importante: a pasta samples/ não vai para o Git (são dados de treino reais).
Por isso, se o PDF não estiver presente, o teste é PULADO (skip) em vez de
falhar — assim quem clonar o repositório sem os PDFs não vê erro falso.

Os valores esperados abaixo foram conferidos diretamente no PDF e cruzados
com a tabela-resumo "QualifyReduced" (que traz a contagem oficial de voltas).
Nada aqui é "chutado".
"""

from pathlib import Path

import pytest

from app.parser.laptimes_parser import parse_laptimes_pdf

# Caminho do PDF real: backend/tests/ -> sobe 2 níveis até a raiz -> samples/
PDF_EXEMPLO = (
    Path(__file__).resolve().parents[2]
    / "samples"
    / "MBR - 4o TREINO OFICIAL MBR - GRUPO 1 - Laptimes_sec4.pdf"
)

# Contagem oficial de voltas por número de carro (da tabela QualifyReduced).
VOLTAS_OFICIAIS = {
    "171": 10, "411": 9, "197": 9, "82": 10, "98": 9, "899": 9, "11": 10,
    "96": 10, "15": 8, "4": 7, "47": 9, "500": 9, "19": 8, "113": 9, "91": 10,
    "328": 10, "225": 10, "707": 7, "25": 10, "66": 7, "122": 6, "38": 10,
    "18": 6, "422": 8, "55": 9, "8": 5,
}


# Roda o parser uma vez só e reaproveita o resultado em todos os testes.
@pytest.fixture(scope="module")
def resultado():
    if not PDF_EXEMPLO.exists():
        pytest.skip(f"PDF de exemplo não encontrado em {PDF_EXEMPLO}")
    return parse_laptimes_pdf(str(PDF_EXEMPLO))


def test_quantidade_de_pilotos(resultado):
    assert len(resultado.pilotos) == 26


def test_contagem_de_voltas_bate_com_a_oficial(resultado):
    """A contagem de voltas de cada piloto deve bater com a tabela oficial.

    Isso valida, entre outras coisas, que voltas que cruzam a quebra de
    página (continuação sem cabeçalho) foram corretamente atribuídas.
    """
    extraidas = {p.numero_carro: p.numero_de_voltas for p in resultado.pilotos}
    assert extraidas == VOLTAS_OFICIAIS


def test_continuacao_entre_paginas(resultado):
    """C.RIBAS/R.FILHO (98) tem 3 voltas no fim de uma coluna e continua na
    coluna seguinte; o total deve ser 9 voltas sequenciais (1..9)."""
    ribas = next(p for p in resultado.pilotos if p.numero_carro == "98")
    assert [v.numero_volta for v in ribas.voltas] == [1, 2, 3, 4, 5, 6, 7, 8, 9]


def test_valores_de_uma_volta_conhecida(resultado):
    """Confere os tempos da volta 2 de L.JOSE (171), que tem todos os campos.

    PDF: lap 2 = 2:21.904, S1 38.404, S2 50.953, S3 52.547, radar 178,2.
    """
    ljose = next(p for p in resultado.pilotos if p.numero_carro == "171")
    v2 = next(v for v in ljose.voltas if v.numero_volta == 2)
    assert v2.tempo_volta_s == pytest.approx(141.904)  # 2*60 + 21.904
    assert v2.setores_s[0] == pytest.approx(38.404)
    assert v2.setores_s[1] == pytest.approx(50.953)
    assert v2.setores_s[2] == pytest.approx(52.547)
    assert v2.velocidade_radar_kmh == pytest.approx(178.2)
    assert v2.campos_ausentes == []


def test_campo_ausente_nao_e_inventado(resultado):
    """A volta 1 de L.JOSE não tem S1 no PDF. O parser deve deixar None e
    sinalizar em campos_ausentes — NUNCA preencher com 0 ou estimativa."""
    ljose = next(p for p in resultado.pilotos if p.numero_carro == "171")
    v1 = next(v for v in ljose.voltas if v.numero_volta == 1)
    assert v1.setores_s[0] is None
    assert "setor1_s" in v1.campos_ausentes
    # Os demais campos da volta 1 existem e não devem estar na lista de ausentes.
    assert v1.tempo_volta_s == pytest.approx(143.983)  # 2:23.983
    assert v1.setores_s[1] == pytest.approx(55.834)


def test_volta_de_pit_e_marcada(resultado):
    """A volta 5 de L.JOSE vem marcada com 'p' no PDF (entrada/saída de box)."""
    ljose = next(p for p in resultado.pilotos if p.numero_carro == "171")
    v5 = next(v for v in ljose.voltas if v.numero_volta == 5)
    assert v5.eh_volta_pit is True

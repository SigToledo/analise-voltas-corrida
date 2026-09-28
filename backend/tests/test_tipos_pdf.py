"""
Testes da identificação de relatórios/sessões, do parser de resumo oficial
(QualifyReduced e RaceFull) e do endpoint /analise com dois arquivos —
contra PDFs reais de samples/ (pulados se ausentes: não vão para o Git).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.parser.pdf_texto import LeitorPDF
from app.parser.resumo_parser import parse_resumo_pdf
from app.parser.tipo_pdf import TipoRelatorio, TipoSessao, identificar

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
PDF_LAPTIMES = SAMPLES / "MBR - 4o TREINO OFICIAL MBR - GRUPO 1 - Laptimes_sec4.pdf"
PDF_QUALIFY = SAMPLES / "MBR - 4o TREINO OFICIAL MBR - GRUPO 1 - QualifyReduced.pdf"
PDF_QUALIFY_CLASSE = SAMPLES / "MBR - 4o TREINO OFICIAL MBR - GRUPO 1 - QualifyReduced BY CLASS.pdf"

CASCAVEL = SAMPLES / "5ET - MBR - CASCAVEL"
CASC_TREINO = CASCAVEL / "SEXTA" / "5ET - MBR - 1º TREINO OFICIAL MBR - GRUPO 1 - Laptimes_sec4.pdf"
CASC_RACEFULL = CASCAVEL / "SABADO" / "5ET - MBR - CORRIDA 1 - MBR - RaceFull.pdf"

tem_cuiaba = pytest.mark.skipif(not PDF_LAPTIMES.exists(), reason="PDFs de Cuiabá ausentes")
tem_cascavel = pytest.mark.skipif(not CASC_TREINO.exists(), reason="PDFs de Cascavel ausentes")

client = TestClient(app)


def _identificar(caminho: Path):
    with LeitorPDF(str(caminho)) as leitor:
        return identificar(leitor)


@tem_cuiaba
def test_identifica_laptimes_e_as_duas_variantes_de_resumo():
    assert _identificar(PDF_LAPTIMES).tipo is TipoRelatorio.LAPTIMES
    plano = _identificar(PDF_QUALIFY)
    por_classe = _identificar(PDF_QUALIFY_CLASSE)
    assert plano.tipo is TipoRelatorio.RESUMO and not plano.agrupado_por_classe
    assert por_classe.tipo is TipoRelatorio.RESUMO and por_classe.agrupado_por_classe


@tem_cuiaba
def test_metadados_da_sessao():
    meta = _identificar(PDF_LAPTIMES).metadados
    assert meta.evento == "ET4 - F TRUCK / MBR - 2026"
    assert meta.pista == "AUTODROMO DE CUIABA 4,500 km"
    assert meta.sessao == "4o TREINO OFICIAL MBR - GRUPO 1"
    assert meta.data_hora == "13/06/2026 08:00"
    assert meta.tipo_sessao is TipoSessao.TREINO


@tem_cuiaba
def test_parser_do_resumo_plano():
    r = parse_resumo_pdf(str(PDF_QUALIFY))
    assert len(r.pilotos) == 26
    assert r.avisos == []
    lider = r.pilotos[0]
    assert (lider.posicao, lider.numero_carro, lider.classe) == (1, "171", "ELITE")
    assert lider.diff_s is None  # o líder não tem Diff no PDF
    assert lider.melhor_volta_s == pytest.approx(134.353)
    assert lider.volta_da_melhor == 10
    # nome com espaços e barra é lido inteiro
    assert any(p.nome == "L.ROSA / L.JUNIOR" for p in r.pilotos)


@tem_cuiaba
def test_parser_do_resumo_por_classe():
    r = parse_resumo_pdf(str(PDF_QUALIFY_CLASSE))
    assert {p.classe for p in r.pilotos} == {"ELITE", "MASTER"}
    assert sum(1 for p in r.pilotos if p.classe == "MASTER") == 9


@tem_cascavel
def test_cascavel_radar_spd_e_metadados():
    """Em Cascavel o radar se chama SPD (Cuiabá: SSTRAP) e a pista vem em caixa mista."""
    ident = _identificar(CASC_TREINO)
    assert ident.tipo is TipoRelatorio.LAPTIMES
    assert ident.metadados.pista == "Autódromo Zilmar Beux Cascavel 3,058 km"
    assert ident.metadados.tipo_sessao is TipoSessao.TREINO


@tem_cascavel
def test_racefull_e_resultado_de_corrida_sem_repeticoes():
    """O RaceFull tem as mesmas colunas do resumo, mas é resultado de CORRIDA —
    e imprime a classificação mais de uma vez: cada carro deve aparecer uma vez."""
    ident = _identificar(CASC_RACEFULL)
    assert ident.tipo is TipoRelatorio.RESULTADO_CORRIDA
    assert ident.metadados.tipo_sessao is TipoSessao.CORRIDA
    r = parse_resumo_pdf(str(CASC_RACEFULL))
    carros = [p.numero_carro for p in r.pilotos]
    assert len(carros) == len(set(carros))
    vencedor = r.pilotos[0]
    assert (vencedor.posicao, vencedor.numero_carro, vencedor.voltas) == (1, "77", 23)
    assert any(p.diff_voltas for p in r.pilotos)  # retardatários: "N Laps" de diferença


@tem_cuiaba
def test_analise_recusa_resumo_como_principal():
    """Enviar o resumo no lugar do Laptimes deve dar erro explicando o quê."""
    with PDF_QUALIFY.open("rb") as f:
        resp = client.post("/analise", files={"arquivo": (PDF_QUALIFY.name, f, "application/pdf")})
    assert resp.status_code == 422
    assert "QualifyReduced" in resp.json()["detail"]


@tem_cuiaba
def test_analise_com_resumo_traz_classes():
    with PDF_LAPTIMES.open("rb") as f1, PDF_QUALIFY.open("rb") as f2:
        resp = client.post(
            "/analise",
            files={
                "arquivo": (PDF_LAPTIMES.name, f1, "application/pdf"),
                "resumo": (PDF_QUALIFY.name, f2, "application/pdf"),
            },
        )
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["metadados"]["sessao"] == "4o TREINO OFICIAL MBR - GRUPO 1"
    assert dados["num_setores"] == 3 and dados["tem_radar"] is True
    ljose = next(p for p in dados["pilotos"] if p["numero_carro"] == "171")
    assert ljose["classe"] == "ELITE"
    assert ljose["posicao_oficial"] == 1
    paioli = next(p for p in dados["pilotos"] if p["numero_carro"] == "96")
    assert paioli["classe"] == "MASTER"
    # 26/26 batem com o oficial: nenhuma divergência de melhor volta
    assert not any("Divergência" in a for a in dados["avisos_parsing"])

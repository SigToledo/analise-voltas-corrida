"""
Testes da detecção de tipo de PDF, do parser de resumo (QualifyReduced) e do
endpoint /analise com os dois arquivos, contra os PDFs reais em samples/.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.parser.qualify_parser import parse_qualify_pdf
from app.parser.tipo_pdf import TipoPDF, detectar_tipo_pdf

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
PDF_LAPTIMES = SAMPLES / "MBR - 4o TREINO OFICIAL MBR - GRUPO 1 - Laptimes_sec4.pdf"
PDF_QUALIFY = SAMPLES / "MBR - 4o TREINO OFICIAL MBR - GRUPO 1 - QualifyReduced.pdf"
PDF_QUALIFY_CLASSE = SAMPLES / "MBR - 4o TREINO OFICIAL MBR - GRUPO 1 - QualifyReduced BY CLASS.pdf"

pytestmark = pytest.mark.skipif(
    not PDF_LAPTIMES.exists(), reason="PDFs de exemplo ausentes em samples/"
)

client = TestClient(app)


def test_detecta_os_tres_tipos():
    assert detectar_tipo_pdf(str(PDF_LAPTIMES))[0] is TipoPDF.LAPTIMES
    assert detectar_tipo_pdf(str(PDF_QUALIFY))[0] is TipoPDF.QUALIFY
    assert detectar_tipo_pdf(str(PDF_QUALIFY_CLASSE))[0] is TipoPDF.QUALIFY_POR_CLASSE


def test_metadados_da_sessao():
    _, meta = detectar_tipo_pdf(str(PDF_LAPTIMES))
    assert meta.evento == "ET4 - F TRUCK / MBR - 2026"
    assert "AUTODROMO DE CUIABA" in (meta.pista or "")
    assert meta.sessao == "4o TREINO OFICIAL MBR - GRUPO 1"
    assert meta.data_hora == "13/06/2026 08:00"


def test_parser_do_resumo_plano():
    r = parse_qualify_pdf(str(PDF_QUALIFY), agrupado_por_classe=False)
    assert len(r.pilotos) == 26
    assert r.avisos == []
    lider = r.pilotos[0]
    assert (lider.posicao, lider.numero_carro, lider.classe) == (1, "171", "ELITE")
    assert lider.diff_s is None  # líder não tem Diff no PDF
    assert lider.melhor_volta_s == pytest.approx(134.353)
    # nome com espaços/barra é lido inteiro
    assert any(p.nome == "L.ROSA / L.JUNIOR" for p in r.pilotos)


def test_parser_do_resumo_por_classe():
    r = parse_qualify_pdf(str(PDF_QUALIFY_CLASSE), agrupado_por_classe=True)
    classes = {p.classe for p in r.pilotos}
    assert classes == {"ELITE", "MASTER"}
    assert sum(1 for p in r.pilotos if p.classe == "MASTER") == 9


def test_analise_recusa_resumo_como_principal():
    """Enviar o resumo no lugar do Laptimes deve dar erro explicando o quê."""
    with PDF_QUALIFY.open("rb") as f:
        resp = client.post("/analise", files={"arquivo": (PDF_QUALIFY.name, f, "application/pdf")})
    assert resp.status_code == 422
    assert "QualifyReduced" in resp.json()["detail"]


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
    ljose = next(p for p in dados["pilotos"] if p["numero_carro"] == "171")
    assert ljose["classe"] == "ELITE"
    assert ljose["posicao_oficial"] == 1
    paioli = next(p for p in dados["pilotos"] if p["numero_carro"] == "96")
    assert paioli["classe"] == "MASTER"
    # 26/26 batem com o oficial: nenhuma divergência de melhor volta
    assert not any("Divergência" in a for a in dados["avisos_parsing"])

"""
Testes do endpoint HTTP /analise usando o TestClient do FastAPI (não sobe
servidor de verdade — chama o app em memória).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

PDF_EXEMPLO = (
    Path(__file__).resolve().parents[2]
    / "samples"
    / "MBR - 4o TREINO OFICIAL MBR - GRUPO 1 - Laptimes_sec4.pdf"
)

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_analise_recusa_nao_pdf():
    resp = client.post(
        "/analise", files={"arquivo": ("notas.txt", b"qualquer coisa", "text/plain")}
    )
    assert resp.status_code == 400


def test_analise_recusa_pdf_invalido():
    """Um PDF que não é Laptimes (ou bytes inválidos) deve virar erro 422,
    nunca um resultado inventado."""
    resp = client.post(
        "/analise", files={"arquivo": ("falso.pdf", b"%PDF-1.4 lixo", "application/pdf")}
    )
    assert resp.status_code == 422


def test_analise_pdf_real():
    if not PDF_EXEMPLO.exists():
        pytest.skip(f"PDF de exemplo não encontrado em {PDF_EXEMPLO}")
    with PDF_EXEMPLO.open("rb") as f:
        resp = client.post(
            "/analise",
            files={"arquivo": (PDF_EXEMPLO.name, f, "application/pdf")},
        )
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["num_pilotos"] == 26
    assert dados["arquivo_origem"] == PDF_EXEMPLO.name
    # Volta ideal calculada e com dono de cada setor.
    assert dados["volta_ideal_equipe"]["total_s"] is not None
    # L.JOSE presente com a melhor volta certa.
    ljose = next(p for p in dados["pilotos"] if p["numero_carro"] == "171")
    assert ljose["melhor_volta_s"] == pytest.approx(134.353)
    assert ljose["numero_volta_melhor"] == 10
    # Comparação setor a setor cobre os 3 setores.
    assert [c["setor"] for c in dados["comparacao_setores"]] == [1, 2, 3]

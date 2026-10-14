"""
Testes de QUAL resumo oficial vale quando chegam vários da mesma sessão
(original e retificação; plano e BY CLASS) — app/parser/edicao.py —, da hora
de impressão que decide isso e do que o resumo escolhido faz com os
DESCLASSIFICADOS (status DQ na tela, fora da volta ideal). Os casos reais
usam PDFs de samples/ (fora do Git; pulados se ausentes).
"""

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.parser.edicao import escolher_resumo
from app.parser.pdf_texto import LeitorPDF, TrechoPDF, hora_de_impressao
from app.parser.resumo_parser import PilotoResumo, ResumoOficial
from app.parser.tipo_pdf import desmontar

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
TARUMA = SAMPLES / "8ET - FT - TARUMA"
CORRIDA_2_MBR = SAMPLES / "5ET - MBR - CASCAVEL" / "DOMINGO"
ORIGINAL = TARUMA / "RESULTADO - CLASSIFICATORIO (FT BOMBA INJETORA).pdf"
RETIFICACAO = TARUMA / "RESULTADO - CLASSIFICATORIO (FT BOMBA INJETORA) - RETIFICACAO.pdf"

client = TestClient(app)


def _resumo(impresso: str | None, por_classe: bool = False, status_77: str | None = None) -> ResumoOficial:
    pilotos = [
        PilotoResumo(posicao=1, numero_carro="7", nome="A", melhor_volta_s=80.0, voltas=10),
        PilotoResumo(
            posicao=None if status_77 else 2, status=status_77, numero_carro="77", nome="B",
            melhor_volta_s=81.0, voltas=9,
        ),
    ]
    return ResumoOficial(
        arquivo_origem="x", tipo="resumo", agrupado_por_classe=por_classe,
        impresso_em=datetime.fromisoformat(impresso) if impresso else None, pilotos=pilotos,
    )


def test_vale_a_edicao_mais_recente_em_qualquer_ordem_e_com_qualquer_nome():
    original = ("resultado.pdf", _resumo("2026-10-10 14:36:12"))
    retificacao = ("outro nome.pdf", _resumo("2026-10-10 17:27:10", status_77="DQ"))
    for ordem in ([original, retificacao], [retificacao, original]):
        (nome, r), avisos = escolher_resumo(ordem)
        assert nome == "outro nome.pdf"
        assert avisos[0] == "Resumo usado: 'outro nome.pdf' (impresso 10/10 às 17:27:10, a edição mais recente)."
        assert "Edição anterior do resumo, não usada: 'resultado.pdf' (impresso 10/10 às 14:36:12)." in avisos


def test_plano_e_by_class_da_mesma_impressao_vale_o_plano():
    """O BY CLASS sai segundos depois do plano, com os mesmos dados: vale o plano (posição geral)."""
    plano = ("RaceFull.pdf", _resumo("2026-09-12 14:42:32"))
    por_classe = ("RaceFull BY CLASS.pdf", _resumo("2026-09-12 14:42:54", por_classe=True))
    (nome, _), avisos = escolher_resumo([por_classe, plano])
    assert nome == "RaceFull.pdf" and len(avisos) == 1


def test_so_o_by_class_retificado_vale_ele_e_avisa_da_posicao():
    plano_antigo = ("RaceFull.pdf", _resumo("2026-09-12 14:42:32"))
    classe_nova = ("RaceFull BY CLASS - RETIFICADO.pdf", _resumo("2026-09-12 17:33:29", True, "DQ"))
    (nome, _), avisos = escolher_resumo([plano_antigo, classe_nova])
    assert nome == "RaceFull BY CLASS - RETIFICADO.pdf"
    assert any("posição geral fica de fora" in a for a in avisos)


def test_sem_hora_de_impressao_cai_para_o_nome_do_arquivo():
    original = ("RESULTADO.pdf", _resumo(None))
    retificacao = ("RESULTADO - RETIFICAÇÃO.pdf", _resumo(None, status_77="DQ"))
    (nome, _), avisos = escolher_resumo([retificacao, original])
    assert nome == "RESULTADO - RETIFICAÇÃO.pdf"
    assert "pelo nome do arquivo" in avisos[0]

    r1 = ("RaceFull - RETIFICADO.pdf", _resumo(None))
    r2 = ("RaceFull - RETIFICADO 2.pdf", _resumo(None))
    assert escolher_resumo([r2, r1])[0][0] == "RaceFull - RETIFICADO 2.pdf"


@pytest.mark.skipif(not RETIFICACAO.exists(), reason="PDFs de Tarumã ausentes")
def test_hora_de_impressao_mesmo_com_o_carimbo_da_assinatura_por_cima():
    """No documento assinado, 'ASSINADO DIGITALMENTE POR:' se mistura à linha do 'Printed:'."""
    with LeitorPDF(str(ORIGINAL)) as leitor:
        resumo = desmontar(leitor)[0]
        assert hora_de_impressao(TrechoPDF(leitor, resumo.paginas)) == datetime(2026, 10, 10, 14, 36, 12)
    with LeitorPDF(str(RETIFICACAO)) as leitor:
        assert hora_de_impressao(TrechoPDF(leitor, [0])) == datetime(2026, 10, 10, 17, 27, 10)


def _pares_original_retificado() -> list[tuple[Path, Path]]:
    """(original, retificado) de resumos em samples/: mesmo nome sem o ' - RETIFICADO…'."""
    if not SAMPLES.exists():
        return []
    pares = []
    for ret in sorted(SAMPLES.rglob("*RETIFICADO*.pdf")):
        if "QualifyReduced" not in ret.name and "RaceFull" not in ret.name:
            continue
        original = ret.with_name(ret.name.split(" - RETIFICADO")[0] + ".pdf")
        if original.exists():
            pares.append((original, ret))
    return pares


@pytest.mark.skipif(not _pares_original_retificado(), reason="PDFs de Cascavel ausentes")
def test_retificacao_foi_impressa_depois_do_original():
    """A premissa da regra: em todo par de samples/, a retificação sai depois."""
    from app.parser.resumo_parser import parse_resumo_pdf

    pares = _pares_original_retificado()
    for original, ret in pares:
        assert parse_resumo_pdf(str(ret)).impresso_em > parse_resumo_pdf(str(original)).impresso_em, ret.name
    assert len(pares) >= 6


@pytest.mark.skipif(not RETIFICACAO.exists(), reason="PDFs de Tarumã ausentes")
def test_api_usa_a_retificacao_de_taruma_em_qualquer_ordem():
    """
    A RETIFICAÇÃO (só o resumo corrigido, sem Laptimes) desclassifica o #550 e o
    #16. Com o nome original (sem "RETIFICADO"), em qualquer ordem, ela vale.
    """
    arquivos = {p: ("arquivos", (p.name, p.read_bytes(), "application/pdf")) for p in (ORIGINAL, RETIFICACAO)}
    for ordem in ([ORIGINAL, RETIFICACAO], [RETIFICACAO, ORIGINAL]):
        d = client.post("/analise", files=[arquivos[p] for p in ordem]).json()
        posicao = {p["numero_carro"]: p["posicao_oficial"] for p in d["pilotos"]}
        assert posicao["550"] is None and posicao["16"] is None
        assert [posicao[c] for c in ("88", "5", "96", "79")] == [12, 13, 14, 15]
        assert f"Resumo usado: '{RETIFICACAO.name} (pág. 1)' (impresso 10/10 às 17:27:10, a edição mais recente)." in d["avisos_parsing"]


def _analisar(*pdfs: Path) -> dict:
    arquivos = [("arquivos", (p.name, p.read_bytes(), "application/pdf")) for p in pdfs]
    resp = client.post("/analise", files=arquivos)
    assert resp.status_code == 200, resp.json()
    return resp.json()


@pytest.mark.skipif(not RETIFICACAO.exists(), reason="PDFs de Tarumã ausentes")
def test_desclassificados_de_taruma_tem_status_e_ficam_fora_da_volta_ideal():
    d = _analisar(ORIGINAL, RETIFICACAO)
    status = {p["numero_carro"]: p["status_oficial"] for p in d["pilotos"]}
    assert {c for c, s in status.items() if s} == {"550", "16"}
    assert status["550"] == status["16"] == "DQ"

    sem = "Sem os desclassificados no resultado oficial: (550) P.GIACOMELLI, (16) G.RAMPON."
    assert sem in d["volta_ideal_equipe"]["avisos"]
    assert sem in d["voltas_ideais_por_classe"]["FT"]["avisos"]
    donos = {s["numero_carro_dono"] for s in d["volta_ideal_equipe"]["setores"]}
    assert donos.isdisjoint({"550", "16"})
    # Os tempos deles continuam os do PDF.
    tempos = {p["numero_carro"]: p["melhor_volta_s"] for p in d["pilotos"]}
    assert tempos["550"] == pytest.approx(89.997) and tempos["16"] == pytest.approx(95.220)

    # Só o original (antes da retificação): ninguém desclassificado.
    d0 = _analisar(ORIGINAL)
    assert all(p["status_oficial"] is None for p in d0["pilotos"])
    assert d0["volta_ideal_equipe"]["avisos"] == []


@pytest.mark.skipif(not CORRIDA_2_MBR.exists(), reason="PDFs de Cascavel ausentes")
def test_corrida_com_desclassificados_em_cascavel():
    """Corrida 2 da MBR: o #3 (SUPER) e o #55 (MASTER) foram desclassificados."""
    d = _analisar(
        CORRIDA_2_MBR / "5ET - MBR - CORRIDA 2 - MBR - Laptimes_sec4.pdf",
        CORRIDA_2_MBR / "5ET - MBR - CORRIDA 2 - MBR - RaceFull.pdf",
    )
    dq = {p["numero_carro"] for p in d["pilotos"] if p["status_oficial"] == "DQ"}
    assert dq == {"3", "55"}
    assert {s["numero_carro_dono"] for s in d["volta_ideal_equipe"]["setores"]}.isdisjoint(dq)
    assert d["voltas_ideais_por_classe"]["SUPER"]["avisos"] == [
        "Sem os desclassificados no resultado oficial: (3) E.Pavelski."
    ]
    # O RaceFull repete "DQ" na coluna Diff: é o status, não leitura ruim.
    assert not any("ilegível ('DQ')" in a for a in d["avisos_parsing"])

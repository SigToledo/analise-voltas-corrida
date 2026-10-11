"""
Testes da identificação de relatórios/sessões, do parser de resumo oficial
(QualifyReduced e RaceFull) e do endpoint /analise com dois arquivos —
contra PDFs reais de samples/ (pulados se ausentes: não vão para o Git).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.parser.laptimes_parser import parse_laptimes
from app.parser.pdf_texto import LeitorPDF, TrechoPDF
from app.parser.resumo_parser import parse_resumo_pdf
from app.parser.tipo_pdf import TipoRelatorio, TipoSessao, desmontar, identificar

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
PDF_LAPTIMES = SAMPLES / "MBR - 4o TREINO OFICIAL MBR - GRUPO 1 - Laptimes_sec4.pdf"
PDF_QUALIFY = SAMPLES / "MBR - 4o TREINO OFICIAL MBR - GRUPO 1 - QualifyReduced.pdf"
PDF_QUALIFY_CLASSE = SAMPLES / "MBR - 4o TREINO OFICIAL MBR - GRUPO 1 - QualifyReduced BY CLASS.pdf"

CASCAVEL = SAMPLES / "5ET - MBR - CASCAVEL"
CASC_TREINO = CASCAVEL / "SEXTA" / "5ET - MBR - 1º TREINO OFICIAL MBR - GRUPO 1 - Laptimes_sec4.pdf"
CASC_RACEFULL = CASCAVEL / "SABADO" / "5ET - MBR - CORRIDA 1 - MBR - RaceFull.pdf"

tem_cuiaba = pytest.mark.skipif(not PDF_LAPTIMES.exists(), reason="PDFs de Cuiabá ausentes")
tem_cascavel = pytest.mark.skipif(not CASC_TREINO.exists(), reason="PDFs de Cascavel ausentes")

# Documento oficial COMPILADO (assinado pelos comissários): resumo + Laptimes
# do Classificatório e do Top Qualifying, mais o consolidado, num PDF só.
TARUMA = SAMPLES / "8ET - FT - TARUMA" / "RESULTADO - CLASSIFICATORIO (FT BOMBA INJETORA).pdf"
tem_taruma = pytest.mark.skipif(not TARUMA.exists(), reason="PDF compilado de Tarumã ausente")

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


@tem_taruma
def test_desmonta_o_documento_oficial_compilado():
    """6 páginas, 5 relatórios: cada um com o tipo, a sessão e as páginas certas."""
    with LeitorPDF(str(TARUMA)) as leitor:
        relatorios = desmontar(leitor)
        laptimes = parse_laptimes(TrechoPDF(leitor, relatorios[1].paginas))

    assert [(r.ident.tipo, r.ident.metadados.sessao, r.descricao_paginas()) for r in relatorios] == [
        (TipoRelatorio.RESUMO, "CLASSIFICATORIO - FT", "pág. 1"),
        (TipoRelatorio.LAPTIMES, "CLASSIFICATORIO - FT", "pág. 2–3"),
        (TipoRelatorio.RESUMO, "TOP QUALIFYING - FT", "pág. 4"),
        (TipoRelatorio.LAPTIMES, "TOP QUALIFYING - FT", "pág. 5"),
        (TipoRelatorio.NAO_SUPORTADO, None, "pág. 6"),
    ]
    assert [r.ident.metadados.data_hora for r in relatorios[:4]] == [
        "10/10/2026 13:40", "10/10/2026 13:40", "10/10/2026 14:10", "10/10/2026 14:10",
    ]
    assert all(r.ident.metadados.tipo_sessao is TipoSessao.QUALY for r in relatorios[:4])
    assert relatorios[4].ident.detalhe == "consolidado de sessões"

    # O Laptimes do Classificatório continua da pág. 2 para a 3 (o #102 começa
    # no fim da pág. 2): 17 carros, nenhum aviso.
    assert len(laptimes.pilotos) == 17 and laptimes.avisos == []
    b_manica = next(p for p in laptimes.pilotos if p.numero_carro == "102")
    assert len(b_manica.voltas) == 12


@tem_taruma
def test_analise_do_documento_compilado_com_as_duas_sessoes():
    """
    O PDF que o app recusava na pista: agora abre o Classificatório (1ª sessão
    do dia) com classe e posição do resumo da pág. 1, e o Top Qualifying fica
    no seletor. Conferido contra o resultado oficial impresso no próprio PDF.
    """
    arquivos = [("arquivos", (TARUMA.name, TARUMA.read_bytes(), "application/pdf"))]
    resp = client.post("/analise", files=arquivos)
    assert resp.status_code == 200, resp.json()
    d = resp.json()
    assert [(s["sessao"], s["data_hora"], s["num_pilotos"], s["arquivos"]) for s in d["sessoes"]] == [
        ("CLASSIFICATORIO - FT", "10/10/2026 13:40", 17, [f"{TARUMA.name} (pág. 2–3)"]),
        ("TOP QUALIFYING - FT", "10/10/2026 14:10", 7, [f"{TARUMA.name} (pág. 5)"]),
    ]
    assert d["sessao_chave"] == d["sessoes"][0]["chave"]
    assert d["arquivo_origem"] == f"{TARUMA.name} (pág. 2–3)"
    assert d["modo"] == "qualy" and d["num_setores"] == 3 and d["tem_radar"]
    # Só o consolidado da pág. 6 é ignorado: sem divergência nem resumo "de fora".
    assert d["avisos_parsing"] == [
        f"Arquivo ignorado — '{TARUMA.name} (pág. 6)': relatório não suportado (consolidado de sessões)."
    ]
    por_carro = {p["numero_carro"]: p for p in d["pilotos"]}
    assert all(p["classe"] == "FT" for p in d["pilotos"])
    conci = por_carro["377"]
    assert conci["posicao_oficial"] == 1 and conci["melhor_volta_s"] == pytest.approx(84.643)
    assert conci["numero_volta_melhor"] == 7
    assert conci["voltas_desconsideradas"] == [2]   # 1:24.337 sem negrito
    assert por_carro["79"]["melhor_volta_s"] is None and por_carro["79"]["posicao_oficial"] == 17

    top = d["sessoes"][1]["chave"]
    d2 = client.post("/analise", files=arquivos, data={"sessao": top}).json()
    assert d2["sessao_chave"] == top and d2["num_pilotos"] == 7
    assert d2["metadados"]["sessao"] == "TOP QUALIFYING - FT"
    por_carro = {p["numero_carro"]: p for p in d2["pilotos"]}
    assert por_carro["377"]["melhor_volta_s"] == pytest.approx(84.842)
    # 275 perdeu a melhor volta por punição (radar): sem volta oficial.
    assert por_carro["275"]["melhor_volta_s"] is None and por_carro["275"]["posicao_oficial"] == 7
    assert any("Carro 440" in a and "sem nenhuma volta" in a for a in d2["avisos_parsing"])

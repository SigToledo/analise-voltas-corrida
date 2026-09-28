"""
Testes da junção de GRUPOS da mesma sessão (MBR: treinos em Grupo 1 e
Grupo 2; classificatório dividido por classe).

A junção em si é simples (concatenar pilotos); o que os testes cobrem de
verdade é a RECUSA: nunca juntar sessões diferentes, dias diferentes, o mesmo
arquivo duas vezes, corrida, ou um carro que aparece em dois grupos.
Os casos reais usam os PDFs de Cascavel em samples/ (fora do Git).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.lap_data import PilotoLaps, ResultadoParsingPDF, VoltaLeitura
from app.parser.juntar import ErroJuncao, ParteSessao, juntar_partes, sigla_do_grupo, siglas_dos_grupos
from app.parser.laptimes_parser import parse_laptimes
from app.parser.pdf_texto import LeitorPDF
from app.parser.tipo_pdf import MetadadosSessao, TipoSessao, identificar

MBR = Path(__file__).resolve().parents[2] / "samples" / "5ET - MBR - CASCAVEL"
client = TestClient(app)

TREINOS = [
    ("SEXTA", "1º TREINO OFICIAL MBR", 25, 18),
    ("SEXTA", "2º TREINO OFICIAL MBR", 26, 19),
    ("SEXTA", "3º TREINO OFICIAL MBR", 26, 18),
    ("SABADO", "4º TREINO OFICIAL MBR", 27, 20),
]


def _parte(caminho: Path) -> ParteSessao:
    with LeitorPDF(str(caminho)) as leitor:
        meta = identificar(leitor).metadados
        return ParteSessao(caminho.name, parse_laptimes(leitor, caminho.name), meta)


def _laptimes(dia: str, sessao: str, grupo: str) -> Path:
    return MBR / dia / f"5ET - MBR - {sessao} - {grupo} - Laptimes_sec4.pdf"


def _exige(*caminhos: Path) -> None:
    for c in caminhos:
        if not c.exists():
            pytest.skip(f"PDF real não encontrado: {c.name}")


def test_sigla_do_grupo():
    assert sigla_do_grupo("GRUPO 1") == "G1"
    assert sigla_do_grupo("Grupo 12") == "G12"
    assert sigla_do_grupo("SUPER") is None


def test_turmas_com_nome_de_classe_viram_g1_g2_pelo_horario():
    """'ELITE/MASTER' e 'SUPER' são turmas com classes misturadas: a etiqueta
    não pode parecer classe."""
    assert siglas_dos_grupos(["GRUPO 1", "GRUPO 2"]) == ["G1", "G2"]
    assert siglas_dos_grupos(["ELITE/MASTER", "SUPER"]) == ["G1", "G2"]
    assert siglas_dos_grupos(["GRUPO 1", "SUPER"]) == ["G1", "G2"]


@pytest.mark.parametrize("dia,sessao,n1,n2", TREINOS)
def test_junta_os_dois_grupos_do_treino(dia, sessao, n1, n2):
    g1, g2 = _laptimes(dia, sessao, "GRUPO 1"), _laptimes(dia, sessao, "GRUPO 2")
    _exige(g1, g2)
    # Ordem trocada de propósito: os grupos saem na ordem do horário.
    resultado, meta, grupos = juntar_partes([_parte(g2), _parte(g1)])
    assert [g.sigla for g in grupos] == ["G1", "G2"]
    assert [g.num_pilotos for g in grupos] == [n1, n2]
    assert len(resultado.pilotos) == n1 + n2
    assert meta.sessao == f"{sessao} - GRUPO 1 + GRUPO 2"
    assert meta.tipo_sessao is TipoSessao.TREINO
    assert {p.grupo for p in resultado.pilotos} == {"G1", "G2"}


def test_junta_o_classificatorio_dividido_por_classe():
    elite = MBR / "SABADO" / "5ET - MBR - CLASSIFICATORIO MBR - ELITE MASTER - Laptimes_sec4.pdf"
    sup = MBR / "SABADO" / "5ET - MBR - CLASSIFICATORIO MBR - SUPER - Laptimes_sec4.pdf"
    _exige(elite, sup)
    resultado, meta, grupos = juntar_partes([_parte(elite), _parte(sup)])
    assert len(resultado.pilotos) == 23 + 24
    assert meta.tipo_sessao is TipoSessao.QUALY
    # Turmas viram G1/G2 pelo horário; o nome oficial fica no rótulo.
    assert [g.sigla for g in grupos] == ["G1", "G2"]
    assert grupos[1].rotulo == "SUPER"
    assert "+" in meta.sessao


def test_recusa_sessoes_diferentes():
    """1º treino G1 + 2º treino G2: mesmo dia, carros diferentes — mas outra sessão."""
    a = _laptimes("SEXTA", "1º TREINO OFICIAL MBR", "GRUPO 1")
    b = _laptimes("SEXTA", "2º TREINO OFICIAL MBR", "GRUPO 2")
    _exige(a, b)
    with pytest.raises(ErroJuncao, match="sessões diferentes"):
        juntar_partes([_parte(a), _parte(b)])


def test_recusa_o_mesmo_relatorio_duas_vezes():
    a = _laptimes("SEXTA", "1º TREINO OFICIAL MBR", "GRUPO 1")
    _exige(a)
    with pytest.raises(ErroJuncao, match="mesmo relatório"):
        juntar_partes([_parte(a), _parte(a)])


def test_recusa_dias_diferentes():
    a = _laptimes("SEXTA", "3º TREINO OFICIAL MBR", "GRUPO 1")
    b = _laptimes("SABADO", "4º TREINO OFICIAL MBR", "GRUPO 2")
    _exige(a, b)
    with pytest.raises(ErroJuncao, match="datas diferentes"):
        juntar_partes([_parte(a), _parte(b)])


def test_recusa_corrida():
    corrida = MBR / "SABADO" / "5ET - MBR - CORRIDA 1 - MBR - Laptimes_sec4.pdf"
    treino = _laptimes("SABADO", "4º TREINO OFICIAL MBR", "GRUPO 1")
    _exige(corrida, treino)
    with pytest.raises(ErroJuncao, match="corrida"):
        juntar_partes([_parte(treino), _parte(corrida)])


def _parte_sintetica(sessao: str, carros: list[str]) -> ParteSessao:
    volta = VoltaLeitura(numero_volta=1, eh_volta_pit=False, tempo_volta_s=80.0, setores_s=[20.0, 40.0, 20.0])
    pilotos = [PilotoLaps(numero_carro=c, nome=f"P{c}", voltas=[volta]) for c in carros]
    meta = MetadadosSessao(
        pista="Pista X", sessao=sessao, data_hora=f"11/09/2026 {'08:45' if 'GRUPO 1' in sessao else '09:10'}",
        tipo_sessao=TipoSessao.TREINO,
    )
    return ParteSessao(f"{sessao}.pdf", ResultadoParsingPDF(arquivo_origem="x", num_setores=3, pilotos=pilotos), meta)


def test_recusa_carro_em_dois_grupos():
    a = _parte_sintetica("TREINO - GRUPO 1", ["7", "77"])
    b = _parte_sintetica("TREINO - GRUPO 2", ["9", "77"])
    with pytest.raises(ErroJuncao, match="carro 77"):
        juntar_partes([a, b])


def test_um_so_laptimes_nao_vira_grupo():
    a = _parte_sintetica("TREINO - GRUPO 1", ["7"])
    resultado, meta, grupos = juntar_partes([a])
    assert grupos == [] and resultado.pilotos[0].grupo is None
    assert meta.sessao == "TREINO - GRUPO 1"


def test_api_junta_grupos_e_casa_cada_resumo_com_o_seu():
    """Os 4 PDFs de uma vez, fora de ordem: cada resumo vai para o seu grupo."""
    base = "1º TREINO OFICIAL MBR"
    nomes = [
        f"5ET - MBR - {base} - GRUPO 2 - Laptimes_sec4.pdf",
        f"5ET - MBR - {base} - GRUPO 1 - QualifyReduced.pdf",
        f"5ET - MBR - {base} - GRUPO 1 - Laptimes_sec4.pdf",
        f"5ET - MBR - {base} - GRUPO 2 - QualifyReduced.pdf",
    ]
    _exige(*(MBR / "SEXTA" / n for n in nomes))
    arquivos = [("arquivos", (n, (MBR / "SEXTA" / n).read_bytes(), "application/pdf")) for n in nomes]
    resp = client.post("/analise", files=arquivos)
    assert resp.status_code == 200, resp.json()
    d = resp.json()
    assert d["num_pilotos"] == 43
    assert [g["sigla"] for g in d["grupos"]] == ["G1", "G2"]
    # Todos com classe e posição DENTRO do próprio grupo (cada grupo começa em P1).
    assert all(p["classe"] and p["posicao_oficial"] for p in d["pilotos"])
    for sigla in ("G1", "G2"):
        posicoes = sorted(p["posicao_oficial"] for p in d["pilotos"] if p["grupo"] == sigla)
        assert posicoes[0] == 1
    # Volta ideal do grid inteiro, com o grupo de cada dono.
    assert all(s["grupo_dono"] in ("G1", "G2") for s in d["volta_ideal_equipe"]["setores"])
    assert not any("Divergência" in a for a in d["avisos_parsing"])

    # Volta ideal de cada classe: dono sempre da própria classe, e nunca mais
    # rápida que a do grid (a do grid escolhe entre TODOS os pilotos).
    classe_do_carro = {p["numero_carro"]: p["classe"] for p in d["pilotos"]}
    por_classe = d["voltas_ideais_por_classe"]
    assert set(por_classe) == {"ELITE", "MASTER", "SUPER"}
    grid = d["volta_ideal_equipe"]["total_s"]
    for classe, ideal in por_classe.items():
        assert ideal["total_s"] >= grid - 1e-9
        assert all(classe_do_carro[s["numero_carro_dono"]] == classe for s in ideal["setores"])

    # Trocar o modo com os mesmos arquivos continua funcionando.
    resp = client.post("/analise", files=arquivos, data={"modo": "qualy"})
    assert resp.status_code == 200 and resp.json()["modo"] == "qualy"


def test_api_recusa_sessoes_diferentes_com_mensagem_clara():
    a = _laptimes("SEXTA", "1º TREINO OFICIAL MBR", "GRUPO 1")
    b = _laptimes("SEXTA", "2º TREINO OFICIAL MBR", "GRUPO 2")
    _exige(a, b)
    arquivos = [("arquivos", (c.name, c.read_bytes(), "application/pdf")) for c in (a, b)]
    resp = client.post("/analise", files=arquivos)
    assert resp.status_code == 422
    assert "sessões diferentes" in resp.json()["detail"]


def test_api_ignora_resumo_de_outra_sessao_com_aviso():
    """Classes e posições de OUTRA sessão seriam dado inventado: o resumo é ignorado."""
    lap = _laptimes("SEXTA", "1º TREINO OFICIAL MBR", "GRUPO 1")
    outro = MBR / "SEXTA" / "5ET - MBR - 2º TREINO OFICIAL MBR - GRUPO 1 - QualifyReduced BY CLASS.pdf"
    _exige(lap, outro)
    arquivos = [("arquivos", (c.name, c.read_bytes(), "application/pdf")) for c in (lap, outro)]
    d = client.post("/analise", files=arquivos).json()
    assert any("ignorado" in a and "2º TREINO" in a for a in d["avisos_parsing"])
    assert all(p["posicao_oficial"] is None for p in d["pilotos"])

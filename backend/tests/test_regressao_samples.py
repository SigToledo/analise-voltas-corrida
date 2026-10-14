"""
REGRESSÃO com todos os PDFs reais de samples/ (inclusive subpastas).

Para cada relatório Laptimes, procura o resumo OFICIAL da mesma sessão
(QualifyReduced em treino/qualy, RaceFull em corrida; prefere a versão
RETIFICADA) e confere, carro a carro:
- a melhor volta do app x o 'Best Tm' oficial;
- a quantidade de voltas lidas x a coluna 'Laps' oficial.

Para validar uma etapa nova, basta colocar os PDFs em samples/ e rodar
`pytest`. Os arquivos não vão para o Git (dados reais de treino): sem eles,
o teste é pulado.
"""

import re
from pathlib import Path

import pytest

from app.metrics.calculations import montar_analise_sessao
from app.models.lap_data import ResultadoParsingPDF
from app.parser.laptimes_parser import parse_laptimes
from app.parser.pdf_texto import LeitorPDF, TrechoPDF
from app.parser.resumo_parser import ResumoOficial, parse_resumo, parse_resumo_pdf
from app.parser.tipo_pdf import SECOES_NAO_CLASSE, TipoRelatorio, desmontar, identificar

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def _pdfs(filtro: str) -> list[Path]:
    if not SAMPLES.exists():
        return []
    return sorted(p for p in SAMPLES.rglob("*.pdf") if "gabarito" not in p.parts and filtro in p.name)


def _resumo_oficial(laptimes: Path) -> Path | None:
    """Resumo da mesma sessão: mesmo prefixo de nome, sem BY CLASS e sem parcial ('VOLTA 10')."""
    prefixo = re.split(r" - Laptimes", laptimes.name)[0]
    candidatos = [
        p for p in laptimes.parent.glob("*.pdf")
        if p.name.startswith(prefixo) and p != laptimes
        and ("QualifyReduced" in p.name or "RaceFull" in p.name)
        and "BY CLASS" not in p.name and "VOLTA" not in p.name
    ]
    if not candidatos:
        return None
    return max(candidatos, key=lambda p: 2 if "RETIFICADO 2" in p.name else 1 if "RETIFICADO" in p.name else 0)


def _parametros(filtro: str):
    pdfs = _pdfs(filtro)
    if not pdfs:
        return [pytest.param(None, marks=pytest.mark.skip(reason="sem PDFs em samples/"))]
    return [pytest.param(p, id=p.stem[-60:]) for p in pdfs]


@pytest.mark.parametrize("laptimes", _parametros("Laptimes"))
def test_laptimes_bate_com_o_resumo_oficial(laptimes: Path):
    with LeitorPDF(str(laptimes)) as leitor:
        assert identificar(leitor).tipo is TipoRelatorio.LAPTIMES
        resultado = parse_laptimes(leitor)
    assert resultado.pilotos, "nenhum piloto lido"
    assert resultado.avisos == [], resultado.avisos[:5]

    oficial = _resumo_oficial(laptimes)
    if oficial is None:
        pytest.skip("sem resumo oficial da mesma sessão")
    erros = _divergencias(resultado, parse_resumo_pdf(str(oficial)))
    assert not erros, erros


def _divergencias(resultado: ResultadoParsingPDF, resumo: ResumoOficial) -> list[str]:
    """Carro a carro: melhor volta do app x 'Best Tm' oficial e voltas lidas x 'Laps'."""
    metricas = {m.numero_carro: m for m in montar_analise_sessao(resultado).pilotos}
    voltas = {p.numero_carro: len(p.voltas) for p in resultado.pilotos}
    erros = []
    for po in resumo.pilotos:
        if po.melhor_volta_s is None:
            continue
        m = metricas.get(po.numero_carro)
        if m is None:
            erros.append(f"carro {po.numero_carro}: está no oficial, não no Laptimes")
            continue
        if m.melhor_volta_s is None or abs(m.melhor_volta_s - po.melhor_volta_s) > 0.0005:
            erros.append(f"carro {po.numero_carro}: melhor volta {m.melhor_volta_s} x oficial {po.melhor_volta_s}")
        if po.voltas is not None and voltas[po.numero_carro] != po.voltas:
            erros.append(f"carro {po.numero_carro}: {voltas[po.numero_carro]} voltas x oficial {po.voltas}")
    return erros


@pytest.mark.parametrize("pdf", _parametros(""))
def test_cada_arquivo_vira_os_seus_relatorios(pdf: Path):
    """
    Identificação página a página (documento oficial compilado):
    - relatório avulso do cronômetro vira UM relatório, com a mesma
      identificação de sempre (pela 1ª página) — nada muda para eles;
    - documento compilado: cada Laptimes dentro dele bate com o resumo da
      MESMA sessão que vem no próprio arquivo. (A RETIFICAÇÃO de Tarumã é um
      compilado só com resumo e consolidado: aí basta o resumo ser lido.)
    """
    with LeitorPDF(str(pdf)) as leitor:
        relatorios = desmontar(leitor)
        if len(relatorios) == 1:
            assert relatorios[0].ident == identificar(leitor)
            assert relatorios[0].paginas == list(range(leitor.num_paginas))
            return

        por_sessao: dict[tuple, dict] = {}
        for r in relatorios:
            trecho = TrechoPDF(leitor, r.paginas)
            chave = (r.ident.metadados.sessao, r.ident.metadados.data_hora)
            if r.ident.tipo is TipoRelatorio.LAPTIMES:
                por_sessao.setdefault(chave, {})["laptimes"] = parse_laptimes(trecho)
            elif r.ident.tipo is TipoRelatorio.RESUMO:
                por_sessao.setdefault(chave, {})["resumo"] = parse_resumo(trecho, r.ident)

    conferidas = 0
    for chave, partes in por_sessao.items():
        if "laptimes" not in partes:
            assert partes["resumo"].pilotos and partes["resumo"].avisos == [], chave
            continue
        resultado = partes["laptimes"]
        assert resultado.pilotos and resultado.avisos == [], (chave, resultado.avisos[:5])
        if "resumo" in partes:
            assert partes["resumo"].avisos == [], (chave, partes["resumo"].avisos)
            erros = _divergencias(resultado, partes["resumo"])
            assert not erros, (chave, erros)
            conferidas += 1
    if any("laptimes" in partes for partes in por_sessao.values()):
        assert conferidas, "documento compilado sem nenhum par Laptimes + resumo"


@pytest.mark.parametrize("relatorio", _parametros("RaceFull") + _parametros("QualifyReduced"))
def test_resumos_oficiais_sao_lidos(relatorio: Path):
    """Todo resumo/resultado de corrida é identificado e rende pilotos sem carro repetido."""
    r = parse_resumo_pdf(str(relatorio))
    carros = [p.numero_carro for p in r.pilotos]
    assert carros and len(carros) == len(set(carros))
    assert all(p.nome for p in r.pilotos)
    # BY CLASS só quando o relatório é mesmo por classe: "Announcements" e
    # "Not classified" são títulos de seção, não classes (antes, isso fazia
    # todo resumo de Cascavel perder a posição oficial).
    assert r.agrupado_por_classe == ("BY CLASS" in relatorio.name.upper())
    assert not any(p.classe and p.classe.lower() in SECOES_NAO_CLASSE for p in r.pilotos)
    if not r.agrupado_por_classe:
        # Classificação geral: posições 1, 2, 3… sem buraco (não classificados sem posição).
        posicoes = [p.posicao for p in r.pilotos if p.posicao is not None]
        assert posicoes == list(range(1, len(posicoes) + 1))

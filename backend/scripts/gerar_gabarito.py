"""
Gera os GABARITOS (golden files) para o porte do motor a TypeScript.

Roda o backend Python (a implementação de referência) sobre TODOS os PDFs de
samples/ (inclusive subpastas) e congela as saídas em JSON. O motor TS só
será aceito quando reproduzir esses arquivos.

Saída em samples/gabarito/, espelhando as subpastas (fora do Git — são dados
reais de treino):
  - <nome>.deteccao.json   tipo de relatório/sessão + metadados do cabeçalho
  - <nome>.parsing.json    resultado bruto do parser (voltas, flags, avisos)
  - <nome>.analise.json    análise completa (métricas, ideal, comparações)
  - <nome>.resumo.json     (só p/ QualifyReduced/RaceFull) parsing do resumo

Documento oficial COMPILADO (vários relatórios num PDF, ver
tipo_pdf.desmontar): um conjunto de arquivos por relatório, com as páginas no
nome — ex.: "<nome>.pag2-3.parsing.json". O motor TS também precisa desmontar.

Uso (a partir de backend/):  venv\\Scripts\\python -m scripts.gerar_gabarito
"""

import json
from pathlib import Path

from app.metrics.calculations import montar_analise_sessao
from app.parser.laptimes_parser import parse_laptimes
from app.parser.pdf_texto import LeitorPDF, TrechoPDF
from app.parser.resumo_parser import parse_resumo
from app.parser.tipo_pdf import Relatorio, TipoRelatorio, TipoSessao, desmontar

RAIZ = Path(__file__).resolve().parents[2]
SAMPLES = RAIZ / "samples"
SAIDA = SAMPLES / "gabarito"


def _salvar(caminho: Path, dados) -> None:
    """JSON determinístico (chaves ordenadas) para diffs estáveis."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _gerar(base: Path, trecho: TrechoPDF, relatorio: Relatorio, nome: str) -> None:
    """Gabaritos de UM relatório (o arquivo inteiro, ou um trecho do compilado)."""
    ident = relatorio.ident
    _salvar(
        base.with_name(base.name + ".deteccao.json"),
        {
            "tipo": ident.tipo.value,
            "agrupado_por_classe": ident.agrupado_por_classe,
            "detalhe": ident.detalhe,
            "metadados": ident.metadados.como_dict(),
            "paginas": [n + 1 for n in relatorio.paginas],
        },
    )
    if ident.tipo is TipoRelatorio.LAPTIMES:
        resultado = parse_laptimes(trecho, nome_arquivo=nome)
        _salvar(base.with_name(base.name + ".parsing.json"), resultado.model_dump())
        # Mesmo modo que a API usa em 'auto': o tipo de sessão do PDF.
        detectado = ident.metadados.tipo_sessao
        analise = montar_analise_sessao(resultado, detectado or TipoSessao.TREINO, detectado)
        analise.metadados = ident.metadados.como_dict()
        _salvar(base.with_name(base.name + ".analise.json"), analise.model_dump())
    elif ident.tipo in (TipoRelatorio.RESUMO, TipoRelatorio.RESULTADO_CORRIDA):
        resumo = parse_resumo(trecho, ident, nome_arquivo=nome)
        _salvar(base.with_name(base.name + ".resumo.json"), resumo.model_dump())


def main() -> None:
    pdfs = sorted(p for p in SAMPLES.rglob("*.pdf") if SAIDA not in p.parents)
    if not pdfs:
        raise SystemExit(f"Nenhum PDF em {SAMPLES} — coloque os relatórios reais lá.")

    contagem: dict[str, int] = {}
    for pdf in pdfs:
        base = SAIDA / pdf.relative_to(SAMPLES).with_suffix("")
        with LeitorPDF(str(pdf)) as leitor:
            relatorios = desmontar(leitor)
            for r in relatorios:
                # Documento compilado (vários relatórios num PDF): um gabarito
                # por relatório, com as páginas no nome do arquivo.
                if len(relatorios) == 1:
                    destino, nome = base, pdf.name
                else:
                    destino = base.with_name(f"{base.name}.pag{r.paginas[0] + 1}-{r.paginas[-1] + 1}")
                    nome = f"{pdf.name} ({r.descricao_paginas()})"
                _gerar(destino, TrechoPDF(leitor, r.paginas), r, nome)
                contagem[r.ident.tipo.value] = contagem.get(r.ident.tipo.value, 0) + 1

    print(f"{len(pdfs)} PDFs processados: {contagem}")
    print(f"Gabaritos em {SAIDA}")


if __name__ == "__main__":
    main()

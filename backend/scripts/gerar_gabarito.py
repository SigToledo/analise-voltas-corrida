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

Uso (a partir de backend/):  venv\\Scripts\\python -m scripts.gerar_gabarito
"""

import json
from pathlib import Path

from app.metrics.calculations import montar_analise_sessao
from app.parser.laptimes_parser import parse_laptimes
from app.parser.pdf_texto import LeitorPDF
from app.parser.resumo_parser import parse_resumo
from app.parser.tipo_pdf import TipoRelatorio, identificar

RAIZ = Path(__file__).resolve().parents[2]
SAMPLES = RAIZ / "samples"
SAIDA = SAMPLES / "gabarito"


def _salvar(caminho: Path, dados) -> None:
    """JSON determinístico (chaves ordenadas) para diffs estáveis."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    pdfs = sorted(p for p in SAMPLES.rglob("*.pdf") if SAIDA not in p.parents)
    if not pdfs:
        raise SystemExit(f"Nenhum PDF em {SAMPLES} — coloque os relatórios reais lá.")

    contagem: dict[str, int] = {}
    for pdf in pdfs:
        base = SAIDA / pdf.relative_to(SAMPLES).with_suffix("")
        with LeitorPDF(str(pdf)) as leitor:
            ident = identificar(leitor)
            _salvar(
                base.with_name(base.name + ".deteccao.json"),
                {
                    "tipo": ident.tipo.value,
                    "agrupado_por_classe": ident.agrupado_por_classe,
                    "detalhe": ident.detalhe,
                    "metadados": ident.metadados.como_dict(),
                },
            )
            if ident.tipo is TipoRelatorio.LAPTIMES:
                resultado = parse_laptimes(leitor, nome_arquivo=pdf.name)
                _salvar(base.with_name(base.name + ".parsing.json"), resultado.model_dump())
                analise = montar_analise_sessao(resultado)
                analise.metadados = ident.metadados.como_dict()
                _salvar(base.with_name(base.name + ".analise.json"), analise.model_dump())
            elif ident.tipo in (TipoRelatorio.RESUMO, TipoRelatorio.RESULTADO_CORRIDA):
                resumo = parse_resumo(leitor, ident, nome_arquivo=pdf.name)
                _salvar(base.with_name(base.name + ".resumo.json"), resumo.model_dump())
        contagem[ident.tipo.value] = contagem.get(ident.tipo.value, 0) + 1

    print(f"{len(pdfs)} PDFs processados: {contagem}")
    print(f"Gabaritos em {SAIDA}")


if __name__ == "__main__":
    main()

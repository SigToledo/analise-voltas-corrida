"""
M0 — Gera os GABARITOS (golden files) para o porte do motor a TypeScript.

Roda o backend Python (a implementação de referência, validada 26/26 contra
o cronômetro oficial) sobre os PDFs reais de samples/ e congela as saídas em
JSON. O futuro motor TS só será aceito quando reproduzir esses arquivos
exatamente (tolerância de 1e-9 em números).

Saída em samples/gabarito/ (fora do Git — são dados reais de treino):
  - <nome>.deteccao.json   tipo detectado + metadados do cabeçalho
  - <nome>.parsing.json    resultado bruto do parser (voltas, flags, avisos)
  - <nome>.analise.json    análise completa (métricas, ideal, comparações)
  - <nome>.resumo.json     (só p/ QualifyReduced) parsing do resumo

Uso (a partir de backend/):  venv\\Scripts\\python -m scripts.gerar_gabarito
"""

import json
from pathlib import Path

from app.metrics.calculations import montar_analise_sessao
from app.parser.laptimes_parser import parse_laptimes_pdf
from app.parser.qualify_parser import parse_qualify_pdf
from app.parser.tipo_pdf import TipoPDF, detectar_tipo_pdf

RAIZ = Path(__file__).resolve().parents[2]
SAMPLES = RAIZ / "samples"
SAIDA = SAMPLES / "gabarito"


def _salvar(caminho: Path, dados) -> None:
    """JSON determinístico (chaves ordenadas) para diffs estáveis."""
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"  gravado {caminho.relative_to(RAIZ)}")


def main() -> None:
    pdfs = sorted(SAMPLES.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"Nenhum PDF em {SAMPLES} — coloque os relatórios reais lá.")
    SAIDA.mkdir(exist_ok=True)

    for pdf in pdfs:
        base = pdf.stem
        print(f"== {base}")
        tipo, meta = detectar_tipo_pdf(str(pdf))
        _salvar(SAIDA / f"{base}.deteccao.json", {"tipo": tipo.value, "metadados": meta.__dict__})

        if tipo is TipoPDF.LAPTIMES:
            resultado = parse_laptimes_pdf(str(pdf))
            # arquivo_origem vira só o nome (o caminho absoluto muda por máquina)
            resultado.arquivo_origem = pdf.name
            _salvar(SAIDA / f"{base}.parsing.json", resultado.model_dump())
            analise = montar_analise_sessao(resultado)
            analise.metadados = meta.__dict__
            _salvar(SAIDA / f"{base}.analise.json", analise.model_dump())
        elif tipo in (TipoPDF.QUALIFY, TipoPDF.QUALIFY_POR_CLASSE):
            resumo = parse_qualify_pdf(
                str(pdf), agrupado_por_classe=(tipo is TipoPDF.QUALIFY_POR_CLASSE)
            )
            resumo.arquivo_origem = pdf.name
            _salvar(SAIDA / f"{base}.resumo.json", resumo.model_dump())
        else:
            print(f"  AVISO: tipo desconhecido — nenhum gabarito gerado para {base}")

    print("\nGabaritos prontos. O motor TS (fase M1) deve reproduzi-los exatamente.")


if __name__ == "__main__":
    main()

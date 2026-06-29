"""
Ponto de entrada do backend FastAPI.

Rotas:
- GET  /health   -> checagem simples de que o servidor está no ar.
- POST /analise  -> recebe um PDF "Laptimes" e devolve a análise completa
                    (métricas por piloto, volta ideal da equipe e comparação
                    setor a setor). É o que o frontend React vai consumir.

Para rodar em desenvolvimento, a partir da pasta backend/:
    uvicorn app.main:app --reload
"""

import os
import tempfile

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.metrics.calculations import montar_analise_sessao
from app.models.metrics import AnaliseSessao
from app.parser.laptimes_parser import parse_laptimes_pdf

app = FastAPI(title="Análise de Voltas — API", version="0.1.0")

# Libera o frontend (Vite/Tauri em dev) a chamar a API do navegador.
# Em produção isso deve ser restringido aos domínios reais.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Checagem simples: se responder, o servidor está no ar."""
    return {"status": "ok"}


@app.post("/analise", response_model=AnaliseSessao)
async def analisar(arquivo: UploadFile) -> AnaliseSessao:
    """
    Recebe o PDF de Laptimes enviado pelo frontend, processa e devolve a
    análise. O arquivo é gravado num temporário (o pdfplumber precisa de um
    caminho em disco) e apagado em seguida.
    """
    if not arquivo.filename or not arquivo.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .pdf.")

    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    # delete=False no Windows: não dá para reabrir um NamedTemporaryFile aberto.
    # Por isso gravamos, fechamos, usamos o caminho e apagamos no finally.
    temporario = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    try:
        temporario.write(conteudo)
        temporario.close()
        resultado = parse_laptimes_pdf(temporario.name)
    except Exception as erro:  # noqa: BLE001 - queremos virar um 422 amigável
        raise HTTPException(
            status_code=422,
            detail=f"Não foi possível ler este PDF como um relatório Laptimes: {erro}",
        ) from erro
    finally:
        os.unlink(temporario.name)

    if not resultado.pilotos:
        raise HTTPException(
            status_code=422,
            detail="Nenhum piloto encontrado no PDF. Confirme que é o relatório 'Laptimes'.",
        )

    # Preserva o nome original do arquivo enviado (em vez do caminho temporário).
    resultado.arquivo_origem = arquivo.filename
    return montar_analise_sessao(resultado)

"""
Ponto de entrada do backend FastAPI.

Nesta etapa o app existe só para a estrutura do projeto ficar de pé: há
apenas uma rota de "saúde" (/health) para confirmar que o servidor sobe.
A rota de upload de PDF e os endpoints de análise virão em etapas seguintes,
depois que o parser estiver validado (esta etapa atual).

Para rodar em desenvolvimento, a partir da pasta backend/:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

app = FastAPI(title="Análise de Voltas — API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Checagem simples: se responder, o servidor está no ar."""
    return {"status": "ok"}

"""
Ponto de entrada para rodar o backend como um executável (sidecar do Tauri).

Diferente do `uvicorn app.main:app` que usamos em desenvolvimento, aqui
subimos o servidor a partir do objeto `app` já importado (sem reload e sem
string de import). Isso é o que funciona quando o backend está "congelado"
num .exe pelo PyInstaller — não há sistema de arquivos de módulos para o
uvicorn reimportar.

O app de desktop (Tauri) inicia este executável junto com a janela e fala com
ele em http://127.0.0.1:8000.
"""

import os
import sys
import threading

import uvicorn

from app.main import app


def _encerrar_quando_o_pai_morrer() -> None:
    """
    Vigia o stdin: o Tauri mantém um cano (pipe) de stdin aberto enquanto o app
    estiver vivo. Quando o app de desktop fecha ou é morto à força, esse cano
    fecha e a leitura retorna vazio (EOF) — aí encerramos o backend na hora.
    Isso evita deixar o servidor órfão segurando a porta 8000.

    Só ativa quando rodando como sidecar (variável ANALISE_SIDECAR=1, definida
    pelo Tauri), para não atrapalhar a execução direta do .exe em testes.
    """
    try:
        while sys.stdin.readline():
            pass
    except Exception:
        pass
    os._exit(0)


if __name__ == "__main__":
    if os.environ.get("ANALISE_SIDECAR") == "1":
        threading.Thread(target=_encerrar_quando_o_pai_morrer, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

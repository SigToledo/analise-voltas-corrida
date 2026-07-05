"""
Ponto de entrada do backend FastAPI.

Rotas:
- GET  /health   -> checagem simples de que o servidor está no ar.
- POST /analise  -> recebe o PDF "Laptimes" (obrigatório) e, opcionalmente, o
                    resumo "QualifyReduced" da mesma sessão. Detecta o tipo de
                    cada arquivo antes de qualquer parsing: alimentar o parser
                    errado produziria lixo silencioso, então arquivo do tipo
                    errado vira erro claro dizendo O QUE foi enviado.

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
from app.parser.qualify_parser import parse_qualify_pdf
from app.parser.tipo_pdf import TipoPDF, detectar_tipo_pdf

app = FastAPI(title="Análise de Voltas — API", version="0.2.0")

# Libera o frontend (Vite/Tauri em dev) a chamar a API do navegador.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_NOMES_TIPO = {
    TipoPDF.LAPTIMES: "Laptimes (volta a volta)",
    TipoPDF.QUALIFY: "resumo QualifyReduced",
    TipoPDF.QUALIFY_POR_CLASSE: "resumo QualifyReduced BY CLASS",
    TipoPDF.DESCONHECIDO: "formato não reconhecido",
}


@app.get("/health")
def health() -> dict[str, str]:
    """Checagem simples: se responder, o servidor está no ar."""
    return {"status": "ok"}


async def _salvar_temporario(arquivo: UploadFile) -> str:
    """Grava o upload num arquivo temporário e devolve o caminho."""
    if not arquivo.filename or not arquivo.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail=f"'{arquivo.filename}': envie um arquivo .pdf.")
    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail=f"'{arquivo.filename}': arquivo vazio.")
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(conteudo)
    tmp.close()
    return tmp.name


@app.post("/analise", response_model=AnaliseSessao)
async def analisar(arquivo: UploadFile, resumo: UploadFile | None = None) -> AnaliseSessao:
    """
    `arquivo`: o PDF Laptimes — é dele que saem as voltas, setores e radar.
    `resumo` (opcional): um dos QualifyReduced — acrescenta classe (ELITE/
    MASTER) e posição oficial, e serve de conferência cruzada das voltas.
    """
    caminho = await _salvar_temporario(arquivo)
    caminho_resumo = await _salvar_temporario(resumo) if resumo is not None else None
    try:
        # --- 1. Detecta o tipo do arquivo principal ---
        try:
            tipo, metadados = detectar_tipo_pdf(caminho)
        except Exception as erro:
            raise HTTPException(
                status_code=422,
                detail=f"'{arquivo.filename}' não pôde ser lido como PDF: {erro}",
            ) from erro

        if tipo in (TipoPDF.QUALIFY, TipoPDF.QUALIFY_POR_CLASSE):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"'{arquivo.filename}' é o {_NOMES_TIPO[tipo]}, que só tem a melhor "
                    "volta de cada piloto. Para a análise volta a volta, envie o "
                    "relatório 'Laptimes' como arquivo principal — o resumo pode ir "
                    "no campo opcional, para trazer as classes."
                ),
            )
        if tipo is TipoPDF.DESCONHECIDO:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"'{arquivo.filename}' não parece um relatório Orbits/MyLaps "
                    "(Laptimes ou QualifyReduced). Confira o arquivo exportado do cronômetro."
                ),
            )

        # --- 2. Parsing do Laptimes ---
        resultado = parse_laptimes_pdf(caminho)
        if not resultado.pilotos:
            raise HTTPException(
                status_code=422,
                detail="Nenhum piloto encontrado no PDF. Confirme que é o relatório 'Laptimes'.",
            )
        resultado.arquivo_origem = arquivo.filename
        analise = montar_analise_sessao(resultado)
        analise.metadados = metadados.__dict__

        # --- 3. Resumo opcional: classes, posição oficial e conferência ---
        if caminho_resumo is not None:
            _mesclar_resumo(analise, caminho_resumo, resumo.filename)

        return analise
    finally:
        os.unlink(caminho)
        if caminho_resumo is not None:
            os.unlink(caminho_resumo)


def _mesclar_resumo(analise: AnaliseSessao, caminho_resumo: str, nome_arquivo: str) -> None:
    """
    Enriquece a análise com o resumo oficial: classe e posição por carro, e
    valida a contagem de voltas (divergência vira aviso — dado nunca é
    ajustado em silêncio).
    """
    tipo, _ = detectar_tipo_pdf(caminho_resumo)
    if tipo not in (TipoPDF.QUALIFY, TipoPDF.QUALIFY_POR_CLASSE):
        analise.avisos_parsing.append(
            f"Resumo '{nome_arquivo}' ignorado: é {_NOMES_TIPO[tipo]}, não um QualifyReduced."
        )
        return

    r = parse_qualify_pdf(caminho_resumo, agrupado_por_classe=(tipo is TipoPDF.QUALIFY_POR_CLASSE))
    analise.avisos_parsing.extend(f"Resumo: {a}" for a in r.avisos)
    por_carro = {p.numero_carro: p for p in r.pilotos}

    for piloto in analise.pilotos:
        oficial = por_carro.get(piloto.numero_carro)
        if oficial is None:
            analise.avisos_parsing.append(
                f"Carro {piloto.numero_carro} está no Laptimes mas não no resumo oficial."
            )
            continue
        piloto.classe = oficial.classe
        # Na variante BY CLASS a posição reinicia por classe — só é a posição
        # geral no resumo plano.
        if tipo is TipoPDF.QUALIFY:
            piloto.posicao_oficial = oficial.posicao
        # Conferência: melhor volta calculada vs oficial (tolerância 1 ms).
        if (
            piloto.melhor_volta_s is not None
            and abs(piloto.melhor_volta_s - oficial.melhor_volta_s) > 0.001
        ):
            analise.avisos_parsing.append(
                f"Divergência no carro {piloto.numero_carro}: melhor volta calculada "
                f"{piloto.melhor_volta_s:.3f}s difere do resumo oficial {oficial.melhor_volta_s:.3f}s."
            )

    faltantes = set(por_carro) - {p.numero_carro for p in analise.pilotos}
    for carro in sorted(faltantes):
        analise.avisos_parsing.append(
            f"Carro {carro} está no resumo oficial mas não foi lido do Laptimes."
        )

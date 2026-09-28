"""
Ponto de entrada do backend FastAPI.

Rotas:
- GET  /health   -> checagem simples de que o servidor está no ar.
- POST /analise  -> recebe o PDF "Laptimes" (obrigatório) e, opcionalmente, o
                    resumo oficial da mesma sessão (QualifyReduced ou RaceFull).
                    Cada arquivo é IDENTIFICADO antes de qualquer parsing:
                    alimentar o parser errado produziria lixo silencioso, então
                    arquivo do tipo errado vira erro claro dizendo O QUE foi
                    enviado.
                    `modo` (opcional): 'auto' (padrão, lê do PDF), 'treino',
                    'qualy' ou 'corrida' — define as regras de classificação
                    das voltas (ver app/metrics/tipos_volta.py).

Para rodar em desenvolvimento, a partir da pasta backend/:
    uvicorn app.main:app --reload
"""

import os
import tempfile

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.metrics.calculations import montar_analise_sessao
from app.models.metrics import AnaliseSessao
from app.parser.laptimes_parser import parse_laptimes
from app.parser.pdf_texto import LeitorPDF
from app.parser.resumo_parser import parse_resumo
from app.parser.tipo_pdf import NOMES_RELATORIO, Identificacao, TipoRelatorio, TipoSessao, identificar

app = FastAPI(title="Análise de Voltas — API", version="0.4.0")

# Libera o frontend (Vite/Tauri em dev) a chamar a API do navegador.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_TIPOS_RESUMO = (TipoRelatorio.RESUMO, TipoRelatorio.RESULTADO_CORRIDA)
_MODOS = {"auto", *(t.value for t in TipoSessao)}


@app.get("/health")
def health() -> dict[str, str]:
    """Checagem simples: se responder, o servidor está no ar."""
    return {"status": "ok"}


async def _salvar_temporario(arquivo: UploadFile, temporarios: list[str]) -> str:
    """Grava o upload num temporário e o registra em `temporarios` (para apagar depois)."""
    if not arquivo.filename or not arquivo.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail=f"'{arquivo.filename}': envie um arquivo .pdf.")
    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail=f"'{arquivo.filename}': arquivo vazio.")
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    temporarios.append(tmp.name)
    tmp.write(conteudo)
    tmp.close()
    return tmp.name


def _descrever(ident: Identificacao) -> str:
    nome = NOMES_RELATORIO[ident.tipo]
    return f"{nome} ({ident.detalhe})" if ident.detalhe else nome


@app.post("/analise", response_model=AnaliseSessao)
async def analisar(
    arquivo: UploadFile, resumo: UploadFile | None = None, modo: str = Form("auto")
) -> AnaliseSessao:
    """
    `arquivo`: o PDF Laptimes — é dele que saem as voltas, setores e radar.
    `resumo` (opcional): o QualifyReduced (treino/qualy) ou o RaceFull
    (corrida) da mesma sessão — acrescenta classe e posição oficial e confere
    a melhor volta calculada contra a oficial.
    `modo`: 'auto' usa o tipo de sessão escrito no PDF; sem ele, vale treino
    (a regra mais conservadora: nenhuma volta vira Safety Car).
    """
    if modo not in _MODOS:
        raise HTTPException(
            status_code=400, detail=f"Modo '{modo}' inválido: use auto, treino, qualy ou corrida."
        )
    # Todos os temporários ficam numa lista e o `finally` apaga todos — antes,
    # um resumo inválido interrompia a função antes do `try` e o PDF principal
    # ficava esquecido no disco.
    temporarios: list[str] = []
    try:
        caminho = await _salvar_temporario(arquivo, temporarios)
        caminho_resumo = await _salvar_temporario(resumo, temporarios) if resumo else None

        try:
            leitor = LeitorPDF(caminho)
        except Exception as erro:
            raise HTTPException(
                status_code=422, detail=f"'{arquivo.filename}' não pôde ser aberto como PDF: {erro}"
            ) from erro
        with leitor:
            ident = identificar(leitor)
            if ident.tipo in _TIPOS_RESUMO:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"'{arquivo.filename}' é o {_descrever(ident)}, que só traz a melhor volta "
                        "de cada piloto. Para a análise volta a volta, envie o relatório "
                        "'Laptimes' como arquivo principal — o resumo pode ir no campo "
                        "opcional, para trazer classes e posições."
                    ),
                )
            if ident.tipo is not TipoRelatorio.LAPTIMES:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"'{arquivo.filename}': {_descrever(ident)}. O app analisa o relatório "
                        "'Laptimes' (volta a volta) do cronômetro Orbits/MyLaps."
                    ),
                )
            resultado = parse_laptimes(leitor, nome_arquivo=arquivo.filename)

        if not resultado.pilotos:
            raise HTTPException(
                status_code=422,
                detail="Nenhum piloto encontrado no PDF. Confirme que é o relatório 'Laptimes'.",
            )
        detectado = ident.metadados.tipo_sessao
        modo_final = (detectado or TipoSessao.TREINO) if modo == "auto" else TipoSessao(modo)
        analise = montar_analise_sessao(resultado, modo_final, detectado)
        analise.metadados = ident.metadados.como_dict()

        if caminho_resumo is not None:
            _mesclar_resumo(analise, caminho_resumo, resumo.filename)
        return analise
    finally:
        for caminho_tmp in temporarios:
            try:
                os.unlink(caminho_tmp)
            except OSError:
                pass


def _mesclar_resumo(analise: AnaliseSessao, caminho_resumo: str, nome_arquivo: str) -> None:
    """
    Enriquece a análise com o resumo oficial: classe e posição por carro, e
    confere a melhor volta (divergência vira aviso — o dado nunca é ajustado).
    """
    with LeitorPDF(caminho_resumo) as leitor:
        ident = identificar(leitor)
        if ident.tipo not in _TIPOS_RESUMO:
            analise.avisos_parsing.append(
                f"Resumo '{nome_arquivo}' ignorado: é {_descrever(ident)}, não QualifyReduced/RaceFull."
            )
            return
        r = parse_resumo(leitor, ident, nome_arquivo=nome_arquivo)

    analise.avisos_parsing.extend(f"Resumo: {a}" for a in r.avisos)
    por_carro = {p.numero_carro: p for p in r.pilotos}

    for piloto in analise.pilotos:
        oficial = por_carro.get(piloto.numero_carro)
        if oficial is None:
            analise.avisos_parsing.append(
                f"Carro {piloto.numero_carro} está no Laptimes mas não no resumo oficial."
            )
            continue
        if oficial.classe:
            piloto.classe = oficial.classe
        # No BY CLASS a posição reinicia por classe: só vale como posição geral
        # no resumo plano.
        if not r.agrupado_por_classe:
            piloto.posicao_oficial = oficial.posicao
        if (
            piloto.melhor_volta_s is not None
            and oficial.melhor_volta_s is not None
            and abs(piloto.melhor_volta_s - oficial.melhor_volta_s) > 0.0005
        ):
            analise.avisos_parsing.append(
                f"Divergência no carro {piloto.numero_carro}: melhor volta {piloto.melhor_volta_s:.3f}s "
                f"no Laptimes x {oficial.melhor_volta_s:.3f}s no resumo oficial."
            )

    faltantes = set(por_carro) - {p.numero_carro for p in analise.pilotos}
    for carro in sorted(faltantes):
        oficial = por_carro[carro]
        if not oficial.voltas and oficial.melhor_volta_s is None:
            analise.avisos_parsing.append(
                f"Carro {carro}: no resultado oficial sem nenhuma volta completada "
                "(não largou ou abandonou) — por isso não aparece no volta a volta."
            )
        else:
            analise.avisos_parsing.append(
                f"Carro {carro} está no resumo oficial mas não foi lido do Laptimes."
            )

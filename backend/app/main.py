"""
Ponto de entrada do backend FastAPI.

Rotas:
- GET  /health   -> checagem simples de que o servidor está no ar.
- POST /analise  -> recebe os PDFs da sessão: o(s) "Laptimes" (obrigatório;
                    mais de um quando a sessão roda em GRUPOS, como os treinos
                    da MBR) e, opcionalmente, os resumos oficiais
                    (QualifyReduced ou RaceFull) de cada grupo.
                    Cada arquivo é IDENTIFICADO pelo conteúdo antes de
                    qualquer parsing — o usuário pode mandar tudo junto, em
                    qualquer ordem. Arquivo do tipo errado vira erro (ou aviso,
                    se ao lado de um Laptimes válido) dizendo O QUE foi enviado.
                    `modo` (opcional): 'auto' (padrão, lê do PDF), 'treino',
                    'qualy' ou 'corrida' — define as regras de classificação
                    das voltas (ver app/metrics/tipos_volta.py).

Para rodar em desenvolvimento, a partir da pasta backend/:
    uvicorn app.main:app --reload
"""

import os
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.metrics.calculations import montar_analise_sessao
from app.models.metrics import AnaliseSessao, GrupoSessao, MetricasPiloto
from app.parser.juntar import ErroJuncao, ParteSessao, juntar_partes
from app.parser.laptimes_parser import parse_laptimes
from app.parser.pdf_texto import LeitorPDF
from app.parser.resumo_parser import ResumoOficial, parse_resumo
from app.parser.tipo_pdf import NOMES_RELATORIO, Identificacao, TipoRelatorio, TipoSessao, identificar

app = FastAPI(title="Análise de Voltas — API", version="0.5.0")

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
    arquivos: list[UploadFile] = File(default=[]),
    arquivo: UploadFile | None = None,
    resumo: UploadFile | None = None,
    modo: str = Form("auto"),
) -> AnaliseSessao:
    """
    `arquivos`: todos os PDFs da sessão, em qualquer ordem — Laptimes (um por
    grupo) e resumos. `arquivo`/`resumo`: a forma antiga (um Laptimes e um
    resumo), que continua valendo.
    `modo`: 'auto' usa o tipo de sessão escrito no PDF; sem ele, vale treino
    (a regra mais conservadora: nenhuma volta vira Safety Car).
    """
    if modo not in _MODOS:
        raise HTTPException(
            status_code=400, detail=f"Modo '{modo}' inválido: use auto, treino, qualy ou corrida."
        )
    enviados = [a for a in (arquivo, resumo, *arquivos) if a is not None]
    if not enviados:
        raise HTTPException(status_code=400, detail="Envie ao menos o PDF 'Laptimes' da sessão.")

    # Todos os temporários ficam numa lista e o `finally` apaga todos.
    temporarios: list[str] = []
    try:
        laptimes: list[ParteSessao] = []
        resumos: list[tuple[str, Identificacao, ResumoOficial]] = []
        ignorados: list[str] = []
        for upload in enviados:
            caminho = await _salvar_temporario(upload, temporarios)
            try:
                leitor = LeitorPDF(caminho)
            except Exception as erro:
                raise HTTPException(
                    status_code=422, detail=f"'{upload.filename}' não pôde ser aberto como PDF: {erro}"
                ) from erro
            with leitor:
                ident = identificar(leitor)
                if ident.tipo is TipoRelatorio.LAPTIMES:
                    lido = parse_laptimes(leitor, nome_arquivo=upload.filename)
                    if not lido.pilotos:
                        raise HTTPException(
                            status_code=422,
                            detail=f"Nenhum piloto encontrado em '{upload.filename}'. "
                            "Confirme que é o relatório 'Laptimes'.",
                        )
                    laptimes.append(ParteSessao(upload.filename, lido, ident.metadados))
                elif ident.tipo in _TIPOS_RESUMO:
                    resumos.append((upload.filename, ident, parse_resumo(leitor, ident, upload.filename)))
                else:
                    ignorados.append(f"'{upload.filename}': {_descrever(ident)}")

        if not laptimes:
            if resumos:
                nome, ident, _ = resumos[0]
                detalhe = (
                    f"'{nome}' é o {_descrever(ident)}, que só traz a melhor volta de cada "
                    "piloto. Para a análise volta a volta, envie também o relatório 'Laptimes' "
                    "— o resumo vai junto, para trazer classes e posições."
                )
            else:
                detalhe = (
                    f"{ignorados[0]}. O app analisa o relatório 'Laptimes' (volta a volta) "
                    "do cronômetro Orbits/MyLaps."
                )
            raise HTTPException(status_code=422, detail=detalhe)

        try:
            resultado, metadados, grupos = juntar_partes(laptimes)
        except ErroJuncao as erro:
            raise HTTPException(status_code=422, detail=str(erro)) from erro

        detectado = metadados.tipo_sessao
        modo_final = (detectado or TipoSessao.TREINO) if modo == "auto" else TipoSessao(modo)
        analise = montar_analise_sessao(resultado, modo_final, detectado)
        analise.metadados = metadados.como_dict()
        analise.grupos = grupos
        analise.avisos_parsing.extend(f"Arquivo ignorado — {i}." for i in ignorados)
        _aplicar_resumos(analise, laptimes, grupos, resumos)
        return analise
    finally:
        for caminho_tmp in temporarios:
            try:
                os.unlink(caminho_tmp)
            except OSError:
                pass


def _prioridade(nome: str, r: ResumoOficial) -> tuple:
    """Resumo preferido de uma sessão: o geral (não BY CLASS) e o retificado mais novo."""
    retificado = 2 if "RETIFICADO 2" in nome.upper() else 1 if "RETIFICADO" in nome.upper() else 0
    return (not r.agrupado_por_classe, retificado)


def _aplicar_resumos(
    analise: AnaliseSessao,
    laptimes: list[ParteSessao],
    grupos: list[GrupoSessao],
    resumos: list[tuple[str, Identificacao, ResumoOficial]],
) -> None:
    """
    Casa cada resumo com o SEU Laptimes pela sessão e horário (conferido nos
    36 pares de Cascavel e Cuiabá: sempre idênticos) e aplica só aos pilotos
    daquele grupo. Resumo de outra sessão é ignorado com aviso — aplicar
    classes e posições de outra sessão seria inventar dado.
    """
    grupo_da_sessao: dict[tuple, str | None] = {
        (p.metadados.sessao, p.metadados.data_hora): None for p in laptimes
    }
    for g in grupos:
        grupo_da_sessao[(g.sessao, g.data_hora)] = g.sigla

    escolhidos: dict[tuple, tuple[str, ResumoOficial]] = {}
    for nome, ident, r in resumos:
        chave = (ident.metadados.sessao, ident.metadados.data_hora)
        if chave not in grupo_da_sessao:
            analise.avisos_parsing.append(
                f"Resumo '{nome}' ignorado: é da sessão '{ident.metadados.sessao}' "
                f"({ident.metadados.data_hora}), que não está entre os Laptimes enviados."
            )
            continue
        atual = escolhidos.get(chave)
        if atual is None:
            escolhidos[chave] = (nome, r)
        elif _prioridade(nome, r) > _prioridade(*atual):
            analise.avisos_parsing.append(f"Resumo '{atual[0]}' não usado: '{nome}' é da mesma sessão.")
            escolhidos[chave] = (nome, r)
        else:
            analise.avisos_parsing.append(f"Resumo '{nome}' não usado: '{atual[0]}' é da mesma sessão.")

    for chave, (_, r) in escolhidos.items():
        grupo = grupo_da_sessao[chave]
        alvo = [p for p in analise.pilotos if p.grupo == grupo]
        _mesclar_resumo(analise, alvo, r, prefixo=f"{grupo}: " if grupo else "")


def _mesclar_resumo(
    analise: AnaliseSessao, pilotos: list[MetricasPiloto], r: ResumoOficial, prefixo: str = ""
) -> None:
    """
    Enriquece os pilotos com o resumo oficial: classe e posição por carro, e
    confere a melhor volta (divergência vira aviso — o dado nunca é ajustado).
    """
    analise.avisos_parsing.extend(f"{prefixo}Resumo: {a}" for a in r.avisos)
    por_carro = {p.numero_carro: p for p in r.pilotos}

    for piloto in pilotos:
        oficial = por_carro.get(piloto.numero_carro)
        if oficial is None:
            analise.avisos_parsing.append(
                f"{prefixo}Carro {piloto.numero_carro} está no Laptimes mas não no resumo oficial."
            )
            continue
        if oficial.classe:
            piloto.classe = oficial.classe
        # No BY CLASS a posição reinicia por classe: só vale como posição no
        # resumo plano.
        if not r.agrupado_por_classe:
            piloto.posicao_oficial = oficial.posicao
        if (
            piloto.melhor_volta_s is not None
            and oficial.melhor_volta_s is not None
            and abs(piloto.melhor_volta_s - oficial.melhor_volta_s) > 0.0005
        ):
            analise.avisos_parsing.append(
                f"{prefixo}Divergência no carro {piloto.numero_carro}: melhor volta "
                f"{piloto.melhor_volta_s:.3f}s no Laptimes x {oficial.melhor_volta_s:.3f}s no resumo oficial."
            )

    faltantes = set(por_carro) - {p.numero_carro for p in pilotos}
    for carro in sorted(faltantes):
        oficial = por_carro[carro]
        if not oficial.voltas and oficial.melhor_volta_s is None:
            analise.avisos_parsing.append(
                f"{prefixo}Carro {carro}: no resultado oficial sem nenhuma volta completada "
                "(não largou ou abandonou) — por isso não aparece no volta a volta."
            )
        else:
            analise.avisos_parsing.append(
                f"{prefixo}Carro {carro} está no resumo oficial mas não foi lido do Laptimes."
            )

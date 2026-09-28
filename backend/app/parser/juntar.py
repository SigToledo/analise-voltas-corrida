"""
Juntar GRUPOS da mesma sessão numa análise só.

Na MBR, cada treino roda em dois grupos (GRUPO 1 e GRUPO 2) e o
classificatório se divide por classe (ELITE/MASTER e SUPER). O cronômetro
gera um Laptimes para cada grupo; o engenheiro quer comparar pilotos dos dois.

A junção é só uma CONCATENAÇÃO de pilotos (cada piloto só tem voltas no
próprio grupo, então nenhuma métrica muda) — o cuidado todo está em NÃO
juntar o que não é da mesma sessão. Só juntamos quando:
- mesma pista, mesmo dia, mesmo tipo de sessão (treino ou qualy — corrida é
  uma sessão só) e as mesmas colunas (setores, radar, negrito);
- os nomes das sessões só diferem no GRUPO ("1º TREINO OFICIAL MBR - GRUPO 1"
  e "... - GRUPO 2"): assim "1º treino G1" + "2º treino G2" é recusado;
- nenhum carro aparece em dois grupos (nos 4 treinos e no classificatório de
  Cascavel, nenhum repete) e nenhum relatório foi enviado duas vezes.
Qualquer falha vira ErroJuncao com o motivo — nunca uma junção "no chute".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.lap_data import ResultadoParsingPDF
from app.models.metrics import GrupoSessao
from app.parser.tipo_pdf import MetadadosSessao, TipoSessao

_SEPARADOR = " - "


class ErroJuncao(ValueError):
    """Os relatórios enviados não são grupos da mesma sessão."""


@dataclass
class ParteSessao:
    """Um Laptimes já lido, com o cabeçalho da sessão."""

    arquivo: str
    resultado: ResultadoParsingPDF
    metadados: MetadadosSessao


def sigla_do_grupo(rotulo: str) -> str:
    """'GRUPO 2' -> 'G2'; outros nomes ('SUPER', 'ELITE/MASTER') ficam como estão."""
    achado = re.fullmatch(r"GRUPO\s*(\d+)", rotulo.strip(), flags=re.IGNORECASE)
    return f"G{achado.group(1)}" if achado else rotulo.strip()


def _rotulos(sessoes: list[str]) -> tuple[int, list[str]]:
    """
    Posição do trecho que diferencia as sessões e o rótulo de cada uma.
    '1º TREINO OFICIAL MBR - GRUPO 1' / '... - GRUPO 2' -> (1, ['GRUPO 1', 'GRUPO 2']).
    Erro se o nome difere em mais de um trecho (são sessões diferentes).
    """
    partes = [s.split(_SEPARADOR) for s in sessoes]
    if len({len(p) for p in partes}) != 1:
        raise ErroJuncao(_msg_sessoes(sessoes))
    diferentes = [i for i in range(len(partes[0])) if len({p[i] for p in partes}) > 1]
    if len(diferentes) != 1:
        raise ErroJuncao(_msg_sessoes(sessoes))
    i = diferentes[0]
    return i, [p[i] for p in partes]


def _msg_sessoes(sessoes: list[str]) -> str:
    lista = " × ".join(f"'{s}'" for s in sessoes)
    return (
        f"Os Laptimes são de sessões diferentes ({lista}). Só dá para juntar os GRUPOS "
        "da mesma sessão (ex.: 1º treino Grupo 1 + 1º treino Grupo 2)."
    )


def _mesmo(partes: list[ParteSessao], valor, descricao: str) -> None:
    valores = [valor(p) for p in partes]
    if len(set(valores)) > 1:
        lista = " × ".join(f"'{p.arquivo}': {v}" for p, v in zip(partes, valores))
        raise ErroJuncao(f"Os Laptimes têm {descricao} diferentes ({lista}): não são grupos da mesma sessão.")


def juntar_partes(
    partes: list[ParteSessao],
) -> tuple[ResultadoParsingPDF, MetadadosSessao, list[GrupoSessao]]:
    """
    Junta os Laptimes dos grupos. Com um só, devolve ele mesmo e nenhum grupo
    (a tela não mostra etiqueta de grupo numa sessão única).
    """
    if len(partes) == 1:
        p = partes[0]
        return p.resultado, p.metadados, []

    for p in partes:
        if p.metadados.tipo_sessao is TipoSessao.CORRIDA:
            raise ErroJuncao(
                f"'{p.arquivo}' é de corrida — a corrida é uma sessão só, sem grupos. "
                "Envie um Laptimes de corrida por vez."
            )

    vistos: dict[tuple, str] = {}
    for p in partes:
        chave = (p.metadados.sessao, p.metadados.data_hora)
        if chave in vistos:
            raise ErroJuncao(
                f"'{vistos[chave]}' e '{p.arquivo}' são o mesmo relatório "
                f"({p.metadados.sessao}, {p.metadados.data_hora}) — envie cada grupo uma vez só."
            )
        vistos[chave] = p.arquivo

    _mesmo(partes, lambda p: p.metadados.pista, "pistas")
    _mesmo(partes, lambda p: (p.metadados.data_hora or "").split(" ")[0], "datas")
    _mesmo(partes, lambda p: p.metadados.tipo_sessao.value if p.metadados.tipo_sessao else None, "tipos de sessão")
    _mesmo(partes, lambda p: p.resultado.num_setores, "números de setores")
    _mesmo(partes, lambda p: p.resultado.tem_radar, "colunas de radar")
    _mesmo(
        partes,
        lambda p: any(v.melhor_oficial for pil in p.resultado.pilotos for v in pil.voltas),
        "marcações de melhor volta (negrito)",
    )

    donos: dict[str, str] = {}
    for p in partes:
        for pil in p.resultado.pilotos:
            if pil.numero_carro in donos:
                raise ErroJuncao(
                    f"O carro {pil.numero_carro} aparece em '{donos[pil.numero_carro]}' e em "
                    f"'{p.arquivo}'. Grupos da mesma sessão não repetem carro — confira os arquivos."
                )
            donos[pil.numero_carro] = p.arquivo

    # Grupos na ordem do horário (o Grupo 1 anda antes do Grupo 2).
    ordenadas = sorted(partes, key=lambda p: (_hora(p.metadados.data_hora), p.metadados.sessao or ""))
    posicao, rotulos = _rotulos([p.metadados.sessao or p.arquivo for p in ordenadas])

    grupos: list[GrupoSessao] = []
    pilotos = []
    avisos: list[str] = []
    for p, rotulo in zip(ordenadas, rotulos):
        sigla = sigla_do_grupo(rotulo)
        for pil in p.resultado.pilotos:
            pilotos.append(pil.model_copy(update={"grupo": sigla}))
        avisos.extend(f"{sigla}: {a}" for a in p.resultado.avisos)
        grupos.append(
            GrupoSessao(
                sigla=sigla, rotulo=rotulo, sessao=p.metadados.sessao,
                data_hora=p.metadados.data_hora, arquivo=p.arquivo,
                num_pilotos=len(p.resultado.pilotos),
            )
        )

    base = ordenadas[0]
    trechos = (base.metadados.sessao or "").split(_SEPARADOR)
    trechos[posicao] = " + ".join(rotulos)
    metadados = MetadadosSessao(
        evento=base.metadados.evento,
        etapa=base.metadados.etapa,
        pista=base.metadados.pista,
        sessao=_SEPARADOR.join(trechos),
        data_hora=base.metadados.data_hora,
        duracao=" | ".join(dict.fromkeys(p.metadados.duracao for p in ordenadas if p.metadados.duracao)) or None,
        tipo_sessao=base.metadados.tipo_sessao,
    )
    resultado = ResultadoParsingPDF(
        arquivo_origem=" + ".join(p.arquivo for p in ordenadas),
        num_setores=base.resultado.num_setores,
        tem_radar=base.resultado.tem_radar,
        pilotos=pilotos,
        avisos=avisos,
    )
    return resultado, metadados, grupos


def _hora(data_hora: str | None) -> str:
    """'11/09/2026 8:45' -> '08:45' (ordenável como texto)."""
    if not data_hora or " " not in data_hora:
        return ""
    h, _, m = data_hora.split(" ")[1].partition(":")
    return f"{int(h):02d}:{m}" if h.isdigit() else data_hora

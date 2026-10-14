"""
Qual resumo oficial vale quando chegam MAIS DE UM da mesma sessão.

A direção de prova retifica resultados (desclassificação, volta cancelada,
punição) publicando uma nova EDIÇÃO do resumo. E o cronômetro imprime o mesmo
resultado em duas variantes, plana e BY CLASS, com segundos de diferença.
A regra:

1. Vale a edição MAIS RECENTE, pela hora de impressão do rodapé
   ("Printed:"). Conferido nos 8 pares original x retificação de Cascavel e
   Tarumã: a retificação é sempre impressa depois. Não depende do nome do
   arquivo (o de Tarumã se chama "RETIFICAÇÃO", não "RETIFICADO").
2. Resumos com os MESMOS dados (status, melhor volta, voltas e tempo total
   de cada carro) são a mesma edição — ex.: o plano e o BY CLASS impressos
   juntos (conferido em todas as sessões de samples/). Entre eles vale o
   PLANO, que traz a posição geral (no BY CLASS ela recomeça em cada classe).
3. Sem a hora de impressão em algum deles, cai para o nome do arquivo
   ("RETIFICADO", "RETIFICAÇÃO", "RETIFICADO 2") — e avisa.
"""

from __future__ import annotations

import re

from app.parser.resumo_parser import ResumoOficial

Candidato = tuple[str, ResumoOficial]       # (nome de origem, resumo lido)

_RE_RETIFICACAO = re.compile(r"RETIFICA(?:DO|ÇÃO|CAO)(?:\s*(\d+))?")


def _dados(r: ResumoOficial) -> dict:
    """O que uma retificação muda. Fora: posição, diff e gap (no BY CLASS são
    relativos à classe) e a classe."""
    return {p.numero_carro: (p.status, p.melhor_volta_s, p.voltas, p.tempo_total_s) for p in r.pilotos}


def _quando(r: ResumoOficial) -> str:
    return r.impresso_em.strftime("%d/%m às %H:%M:%S")


def _ordem_pelo_nome(candidato: Candidato) -> tuple:
    """'... RETIFICADO 2' > '... RETIFICAÇÃO' > original; empate: o plano."""
    nome, r = candidato
    achado = _RE_RETIFICACAO.search(nome.upper())
    edicao = (int(achado.group(1)) if achado.group(1) else 1) if achado else 0
    return (edicao, not r.agrupado_por_classe)


def escolher_resumo(candidatos: list[Candidato]) -> tuple[Candidato, list[str]]:
    """O resumo que vale entre os da MESMA sessão, e avisos dizendo qual e por quê."""
    if len(candidatos) == 1:
        return candidatos[0], []

    if all(r.impresso_em is not None for _, r in candidatos):
        mais_novo = max(candidatos, key=lambda c: c[1].impresso_em)
        edicao = _dados(mais_novo[1])
        atuais = [c for c in candidatos if _dados(c[1]) == edicao]
        anteriores = [c for c in candidatos if _dados(c[1]) != edicao]
        escolhido = max(atuais, key=lambda c: (not c[1].agrupado_por_classe, c[1].impresso_em))

        avisos = [f"Resumo usado: '{escolhido[0]}' (impresso {_quando(escolhido[1])}, a edição mais recente)."]
        if anteriores:
            lista = ", ".join(f"'{nome}' (impresso {_quando(r)})" for nome, r in anteriores)
            avisos.append(f"Edição anterior do resumo, não usada: {lista}.")
        if escolhido[1].agrupado_por_classe and any(not r.agrupado_por_classe for _, r in anteriores):
            avisos.append(
                "Só o resumo por classe está na edição mais recente: a posição geral fica de fora "
                "(a do resumo plano é de uma edição anterior)."
            )
        return escolhido, avisos

    escolhido = max(candidatos, key=_ordem_pelo_nome)
    sem_hora = ", ".join(f"'{nome}'" for nome, r in candidatos if r.impresso_em is None)
    return escolhido, [
        f"Sem a hora de impressão em {sem_hora}: não deu para saber qual resumo é o mais recente. "
        f"Usado '{escolhido[0]}', escolhido pelo nome do arquivo."
    ]

# Wireframes e fluxos — telas principais

Fase de design, anterior à implementação. Nenhum código foi escrito a partir
deste documento ainda.

---

## Tela 1 — Upload do PDF de treino

**Hierarquia visual**
- Topo: área central de drop/seleção de arquivo, grande, ocupando a maior
  parte da tela — é a única ação possível nesse momento, então nada compete
  com ela.
- Abaixo, secundário: lista de "Treinos recentes" (sessões já processadas),
  em cards pequenos com nome do evento, data e número de pilotos
  identificados — permite reabrir uma análise sem reprocessar o PDF.
- Rodapé fixo, discreto: indicação do formato esperado ("PDF exportado do
  cronômetro AMB/MyLaps") para reduzir tentativa de upload de arquivo errado.

**Fluxo de interação**
1. Usuário chega na tela vazia, vê botão central **"Selecionar PDF do
   treino"** (ou arrasta o arquivo sobre a área pontilhada).
2. Ao soltar/selecionar, aparece nome do arquivo + botão **"Processar
   treino"**.
3. Sistema extrai dados (backend FastAPI) — tela muda para estado de
   carregamento.
4. Ao concluir, redireciona automaticamente para a Tela 2 (Comparação), já
   com a sessão carregada.

**Estados**
- *Carregando*: barra de progresso ou spinner com status em etapas curtas
  ("Lendo PDF...", "Identificando pilotos...", "Calculando setores...").
  Evita tela em branco — sob pressão de tempo, o usuário precisa saber que
  algo está acontecendo, não se travou.
- *Erro (PDF não reconhecido/corrompido)*: card vermelho/laranja substituindo
  a área de upload: **"Não foi possível ler este PDF. Verifique se é o
  relatório de treino exportado do cronômetro."** Botões: **"Tentar outro
  arquivo"** e **"Ver detalhes do erro"** (expande texto técnico). Nunca
  avança para a Tela 2 com dado parcial.
- *Dados faltando parcialmente* (ex: PDF lido, mas alguns pilotos sem nome
  ou sem voltas válidas): upload é aceito, mas aparece aviso amarelo acima
  da lista de pilotos identificados: **"3 de 8 pilotos sem voltas válidas
  neste treino"** com link **"Ver quais"**. Permite avançar, mas avisa antes
  de decisão com base em dado incompleto.

**Decisão habilitada**: confirmar que o treino certo foi carregado e que os
dados extraídos são confiáveis o suficiente para análise — ou descartar e
tentar de novo, sem perder tempo investigando número errado na Tela 2.

---

## Tela 2 — Comparação entre pilotos

**Hierarquia visual**
- Topo: seletor de até N pilotos (chips clicáveis com nome + melhor tempo de
  volta), pré-selecionados os 2 mais rápidos da sessão por padrão.
- Centro, elemento dominante: gráfico comparativo de tempos por volta (eixo
  X = número da volta, eixo Y = tempo), uma cor por piloto.
- Abaixo do gráfico, secundário: tabela de **melhor volta de cada piloto**
  lado a lado, com delta em relação ao mais rápido (ex: "+0,342s").
- Mais abaixo, terciário: lista de todas as voltas, recolhida por padrão
  ("Ver todas as voltas") — consulta, não decisão imediata.

**Fluxo de interação**
1. Usuário chega da Tela 1 já com pilotos pré-selecionados e gráfico
   renderizado.
2. Clica em chips de outros pilotos para adicionar/remover da comparação
   (limite sugerido: 4 pilotos simultâneos).
3. Passa o mouse/toca numa volta no gráfico para ver tooltip com tempo exato
   e diferença para os outros pilotos naquela volta.
4. Botão **"Ver onde ganhar tempo"** no canto superior direito leva à Tela 3,
   mantendo os pilotos selecionados.

**Estados**
- *Carregando*: skeleton do gráfico (linhas cinzas pulsando) — evita "pulo"
  visual brusco quando os dados chegam.
- *Erro*: se não houver voltas válidas em comum entre os pilotos
  selecionados: **"Não há voltas válidas em comum entre os pilotos
  selecionados."** Botão **"Escolher outros pilotos"**.
- *Dados faltando*: voltas inválidas (boxes, safety car, sensor que não leu)
  aparecem como lacuna visual no gráfico (ponto cinza claro/tracejado, nunca
  interpolado) com tooltip "sem leitura". Se um piloto não tem nenhuma volta
  válida, a célula na tabela de melhor volta mostra **"— sem volta válida"**
  em cor neutra (não vermelho, não zero) — diferenciado de "pior tempo".

**Decisão habilitada**: identificar quem é mais rápido, em que momento da
sessão (ex: perda de ritmo no fim), e escolher quais pilotos aprofundar na
Tela 3.

---

## Tela 3 — "Onde ganhar tempo" (gaps por setor e volta ideal)

**Hierarquia visual**
- Topo, maior destaque visual de toda a tela: card **"Volta ideal da
  equipe"** — soma do melhor tempo de cada setor entre todos os pilotos
  válidos, tempo total em destaque grande, com breakdown por setor mostrando
  qual piloto fez o melhor tempo em cada um.
- Segundo nível: tabela de gaps por setor entre os pilotos comparados (linha
  = setor, coluna = piloto); a célula com maior gap recebe destaque visual
  forte (cor de alerta mais saturada quanto maior o gap) — mapa de calor de
  onde focar o treino.
- Terceiro nível, mais discreto: gráfico de evolução do gap por setor ao
  longo das voltas (mostra se o problema é consistente ou pontual, ex.
  degradação de pneu nas últimas voltas).

**Fluxo de interação**
1. Usuário chega já com o card de volta ideal calculado e a tabela de gaps
   visível, herdando a seleção de pilotos da Tela 2.
2. Clica em um setor na tabela de gaps para expandir detalhe: em qual volta
   aquele gap foi medido; o gráfico de evolução filtra para aquele setor.
3. Botão **"Exportar resumo para a equipe"** gera resumo compacto (texto ou
   imagem) com volta ideal + maiores gaps, para compartilhar entre sessões.
4. Botões secundários **"Comparar outro setor"** / **"Voltar para
   comparação de pilotos"** para ajustar seleção sem perder contexto.

**Estados**
- *Carregando*: card de volta ideal mostra placeholder **"Calculando volta
  ideal..."** — nunca um número transitório como "0:00.000", que poderia ser
  confundido com dado real sob pressão de tempo.
- *Erro*: se nenhum setor puder ter gap calculado (ex: PDF só com tempo de
  volta total, sem segmentação por setor): tabela de gaps é substituída por
  **"Este treino não tem dados de setor — apenas tempo de volta total
  disponível."** com sugestão **"Ver comparação geral de voltas"** (volta à
  Tela 2).
- *Dados faltando por setor* (caso mais crítico de "não inventar dado"): se
  um piloto não tem leitura válida num setor (sensor falhou, transponder não
  passou no ponto), a célula correspondente mostra **"sem leitura"** em
  cinza com ícone de alerta sutil (nunca um traço neutro tipo "não se
  aplica", nunca número estimado/interpolado). Esse piloto é **excluído do
  cálculo da volta ideal naquele setor especificamente**, e isso é indicado
  explicitamente: abaixo do card de volta ideal, texto pequeno **"Setor 2:
  piloto Fulano não incluído (sem leitura)"**. Evita decisão de setup
  baseada em tempo que não foi de fato medido.

**Decisão habilitada**: esta é a tela de ação direta — o engenheiro decide em
qual setor focar ajuste de setup ou orientação ao piloto antes da próxima
sessão (maior gap = maior prioridade), com a "meta" objetiva (volta ideal da
equipe) para comunicar ao piloto entre sessões.

---

## Notas transversais de responsividade (desktop → mobile)

- Nas três telas, os blocos da hierarquia visual empilham verticalmente em
  telas estreitas, mantendo a ordem — o que é primário no desktop continua
  primeiro no celular (nunca reordenar para baixo).
- Tabelas largas (gaps por setor, comparação de pilotos) usam scroll
  horizontal com piloto fixo na primeira coluna, em vez de truncar dados ou
  reduzir fonte a ponto de ficar ilegível sob luz de garagem.
- Todos os estados de "dado faltando" usam o mesmo vocabulário visual (cinza
  + ícone de alerta + texto "sem leitura"/"sem volta válida") nas três
  telas, criando um padrão reconhecível mesmo sob pressão de tempo.

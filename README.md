# Análise de Voltas

Aplicativo de desktop para análise de desempenho em treinos, classificações e
corridas de automobilismo, a partir dos PDFs de cronometragem gerados por
sistemas Orbits/MyLaps. Pensado para o uso de um engenheiro de corrida na
garagem: do PDF da sessão ao "onde ganhar tempo" em poucos cliques.

## O que faz

- **Lê o PDF de Laptimes de qualquer evento.** As colunas são lidas pelo
  TÍTULO (cada evento configura colunas diferentes: o radar é `SPD` em
  Cascavel e `SSTRAP` em Cuiabá; o número de setores varia por pista). Por
  piloto: número do carro, nome, voltas, tempo total, setores e radar.
- **Melhor volta oficial pelo negrito do PDF.** O cronômetro imprime em
  negrito a melhor volta que valeu — já descontadas as voltas canceladas pela
  direção de prova (ex.: limite de pista), que não têm outra marcação. Voltas
  mais rápidas que a oficial aparecem como **desconsideradas**.
- **Classifica cada volta:** lançada, largada, entrada/saída do box, **Safety
  Car** e relargada. O Safety Car não vem marcado no PDF: é detectado quando o
  grid inteiro fica lento ao mesmo tempo (tráfego ou erro afetam um piloto só).
- **Modo Treino / Qualy / Corrida**, lido do PDF e trocável na tela: na
  corrida, a volta 1 é largada, os SCs são detectados e o ritmo é comparado
  entre eles; no treino, por saída do box (antes e depois de um ajuste).
- **Calcula as métricas que decidem ajuste de setup e pilotagem:**
  - melhor volta e a volta em que ocorreu;
  - melhor volta teórica (soma dos melhores setores) e o tempo "deixado na mesa";
  - ritmo pela **mediana** das voltas lançadas e consistência pelo MAD (a
    versão robusta do desvio padrão — uma volta com tráfego não distorce);
  - velocidade de radar máxima e mediana;
  - **volta ideal da equipe** — os melhores setores de todo o grid combinados.
- **Compara pilotos** lado a lado: gráfico de tempo por volta (com faixa de
  Safety Car e marcas de box/largada), ritmo por trecho e mapa de calor de
  gaps por setor (em segundos e %), destacando onde está a maior oportunidade.
- **Usa o resumo oficial** (QualifyReduced ou RaceFull), quando enviado, para
  trazer a classe e a posição de cada carro e conferir a melhor volta.

### Princípio de integridade dos dados

Dados de cronometragem orientam decisões de engenharia, então o app **nunca
inventa um valor que não está no PDF**. Quando uma leitura falta (um setor sem
registro, um piloto sem volta completa), isso aparece explicitamente como
"sem leitura" / "sem volta válida" — nunca preenchido com zero ou estimativa.
O que é inferido (como o Safety Car) aparece como inferência ("provável Safety
Car"), com as voltas e o horário para conferir.

A leitura é validada contra o próprio cronômetro: em 36 relatórios de Cuiabá e
Cascavel (MBR, Fórmula Truck, GT, Fórmula Fusca e Speed Max), a melhor volta e
o número de voltas batem com o resumo oficial em **866 de 866 carros**
(`backend/tests/test_regressao_samples.py`). Para validar uma etapa nova, basta
colocar os PDFs dela em `samples/` e rodar os testes.

## Stack

- **Backend** — Python + FastAPI. Todo o parsing de PDF (com `pdfplumber`) e os
  cálculos. Exposto pelo endpoint `POST /analise`.
- **Frontend** — React + TypeScript (Vite). Visualização e comparação.
- **Desktop** — Tauri (Windows). Empacota o frontend e embute o backend como
  *sidecar*, então o app abre e funciona sozinho, sem terminal.

## Como rodar em desenvolvimento

Pré-requisitos: Python 3.11+, Node.js LTS.

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows (PowerShell: venv\Scripts\Activate.ps1)
pip install -r requirements.txt
uvicorn app.main:app --reload  # sobe em http://localhost:8000
```

Testes:

```bash
pytest                         # precisa dos PDFs de exemplo em samples/ (ver abaixo)
```

### Frontend

```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173 (faz proxy de /analise para o backend)
```

Abra `http://localhost:5173`, envie um PDF de Laptimes (e, se quiser, o resumo
QualifyReduced/RaceFull da mesma sessão) e navegue entre as telas de comparação
e "onde ganhar tempo".

Testes do frontend: `npx vitest run`.

## Empacotar para Windows (instalador)

O app de desktop embute o backend como sidecar. O passo a passo completo
(incluindo gerar o executável do backend com PyInstaller) está em
[docs/empacotamento-windows.md](docs/empacotamento-windows.md). Em resumo, a
partir de `frontend/`:

```bash
npx tauri build   # gera o MSI e o setup.exe em src-tauri/target/release/bundle/
```

## Estrutura

```
backend/    API FastAPI
  app/parser    leitura do PDF: identificação do relatório, colunas pelo título,
                Laptimes e resumos oficiais
  app/metrics   tipo de cada volta (inclui Safety Car) e métricas
frontend/   App React (src/screens, src/components) e projeto Tauri (src-tauri)
docs/       wireframes, guia de empacotamento e plano do app mobile
samples/    PDFs reais das etapas (NÃO versionados)
```

Os PDFs de treino (`samples/`), as dependências (`node_modules/`, `venv/`), os
artefatos de build (`target/`, sidecar) e os instaladores ficam fora do Git.

## Status

Funcionando de ponta a ponta: leitura validada contra o cronômetro, tipos de
volta com Safety Car, modos treino/qualy/corrida, três telas e instalador
Windows standalone. Próximos passos: gráfico de posições da corrida (relatório
Lapchart), cruzar velocidade de radar com tempo de setor (perda em reta vs.
curva), posição dentro da classe e o app mobile ([docs/plano-mobile.md](docs/plano-mobile.md)).

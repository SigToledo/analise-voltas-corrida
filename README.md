# Análise de Voltas

Aplicativo de desktop para análise de desempenho em treinos de automobilismo
(kart e categorias de pista) a partir dos PDFs de cronometragem gerados por
sistemas Orbits/MyLaps. Pensado para o uso de um engenheiro de corrida na
garagem: do PDF do treino ao "onde ganhar tempo" em poucos cliques.

## O que faz

- **Lê o PDF de Laptimes** e extrai, por piloto: número do carro, nome, voltas,
  tempo total, tempos de setor (S1/S2/S3) e velocidade de radar (SSTRAP).
- **Calcula as métricas que decidem ajuste de setup e pilotagem:**
  - melhor volta e a volta em que ocorreu;
  - melhor volta teórica (soma dos melhores setores) e o tempo "deixado na mesa";
  - mediana (ritmo) e desvio padrão (consistência) das voltas válidas;
  - melhor e média de velocidade de radar;
  - **volta ideal da equipe** — os melhores setores de todo o grid combinados.
- **Compara pilotos** lado a lado: gráfico de tempo por volta e mapa de calor de
  gaps por setor (em segundos e %), destacando onde está a maior oportunidade.

### Princípio de integridade dos dados

Dados de cronometragem orientam decisões de engenharia, então o app **nunca
inventa um valor que não está no PDF**. Quando uma leitura falta (um setor sem
registro, um piloto sem volta completa), isso aparece explicitamente como
"sem leitura" / "sem volta válida" — nunca preenchido com zero ou estimativa.
A regra de "volta válida" (não-pit, com os três setores) foi validada contra o
relatório oficial do cronômetro: a melhor volta calculada bate com o `Best Tm`
oficial nos 26 pilotos da sessão de referência.

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

Abra `http://localhost:5173`, envie um PDF de Laptimes e navegue entre as telas
de comparação e "onde ganhar tempo".

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
backend/    API FastAPI: parser de PDF (app/parser) e métricas (app/metrics)
frontend/   App React (src/screens) e projeto Tauri (src-tauri)
docs/        wireframes das telas e guia de empacotamento
samples/     PDFs reais de treino (NÃO versionados)
```

Os PDFs de treino (`samples/`), as dependências (`node_modules/`, `venv/`), os
artefatos de build (`target/`, sidecar) e os instaladores ficam fora do Git.

## Status

Funcionando de ponta a ponta: parsing validado, métricas, três telas e
instalador Windows standalone. Em aberto: extrair metadados do rodapé do PDF
(pista, sessão) e a classe (ELITE/MASTER), cruzar velocidade de radar com tempo
de setor (perda em reta vs. curva) e exercitar os estados de dado faltando com
um PDF incompleto.

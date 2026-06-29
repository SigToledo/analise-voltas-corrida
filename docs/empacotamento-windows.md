# Empacotamento Windows (Tauri)

Como gerar o app de desktop e o instalador para Windows.

## Pré-requisitos (instalados uma vez por máquina)

- **Node.js LTS** (frontend).
- **Rust** atualizado (`rustup update stable` — precisa ser ≥ 1.85, por causa
  da "edition 2024" de dependências do Tauri).
- **MSVC / C++ Build Tools** (vem com o Visual Studio com a carga "Desenvolvimento
  para desktop com C++"). O Rust no Windows usa o linker da Microsoft.
- **WebView2 Runtime** (já vem no Windows 11; no Windows 10 normalmente também).

## Estrutura

O Tauri "embrulha" o frontend React. A configuração fica em
`frontend/src-tauri/` (projeto Rust). Pontos principais de
`frontend/src-tauri/tauri.conf.json`:

- `build.frontendDist`: `../dist` — a pasta que o `npm run build` (Vite) gera.
- `build.devUrl`: `http://localhost:5173` — usado no modo dev.
- `build.beforeBuildCommand`: `npm run build` — o Tauri roda isso antes de
  empacotar, então o frontend é sempre rebuildado.

## Comandos

A partir de `frontend/`:

```powershell
# Rodar o app em modo desenvolvimento (abre a janela nativa, com hot reload):
npx tauri dev

# Gerar os instaladores de produção:
npx tauri build
```

A primeira compilação do Rust é demorada (baixa e compila muitas dependências);
as seguintes são rápidas (cache em `src-tauri/target/`, que NÃO vai para o Git).

### O que `tauri build` gera

Em `frontend/src-tauri/target/release/bundle/`:

- `msi/Analise de Voltas_<versão>_x64_en-US.msi` — instalador MSI.
- `nsis/Analise de Voltas_<versão>_x64-setup.exe` — instalador NSIS (setup.exe).

E o executável solto em `frontend/src-tauri/target/release/` (binário `app.exe`).

## Backend embutido como sidecar (app standalone)

O backend FastAPI (Python) é embutido no app como **sidecar**: um executável
gerado com PyInstaller que o Tauri inicia junto com a janela e encerra quando
o app fecha. Assim o usuário final só instala e abre — sem terminal, sem rodar
servidor à mão.

Como funciona:
- `frontend/src/api.ts`: em produção o frontend fala com `http://localhost:8000`.
- `tauri.conf.json` → `bundle.externalBin`: `binaries/analise-backend` (o Tauri
  procura o arquivo com o sufixo do alvo, ex. `...-x86_64-pc-windows-msvc.exe`).
- `src-tauri/src/lib.rs`: inicia o sidecar no `setup` e o mata no fechamento da
  janela; também define `ANALISE_SIDECAR=1`.
- `backend/run_server.py`: quando `ANALISE_SIDECAR=1`, vigia o stdin e se encerra
  sozinho se o app morrer (inclusive em crash/force-kill), evitando processo
  órfão segurando a porta 8000.

### Gerar/atualizar o sidecar (sempre que o backend mudar)

O binário do sidecar é um artefato de build e **não** vai para o Git (é grande).
Regere-o a partir de `backend/` (com o venv do backend):

```powershell
# 1. Gera o .exe do backend (saída em backend/dist/analise-backend.exe)
.\venv\Scripts\python.exe -m PyInstaller --onefile --name analise-backend `
  --collect-all uvicorn --collect-all pdfplumber --collect-all pdfminer `
  --collect-all fastapi --collect-submodules app --noconfirm run_server.py

# 2. Copia para a pasta de binários do Tauri, COM o sufixo do alvo:
Copy-Item .\dist\analise-backend.exe `
  ..\frontend\src-tauri\binaries\analise-backend-x86_64-pc-windows-msvc.exe -Force
```

Depois rode `npx tauri build` em `frontend/`. Para o `tauri dev`, o sidecar
também é iniciado automaticamente (precisa do binário já copiado em `binaries/`).

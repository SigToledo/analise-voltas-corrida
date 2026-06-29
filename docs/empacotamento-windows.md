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

## IMPORTANTE — backend ainda não embutido (próxima etapa)

Hoje o Tauri empacota apenas o **frontend**. O **backend FastAPI (Python)**, que
faz o parsing do PDF e os cálculos, **não está dentro do executável**.

Consequência: para o app empacotado funcionar, o backend precisa estar rodando
em `http://localhost:8000` (o frontend de produção chama esse endereço — ver
`frontend/src/api.ts`). Em desenvolvimento, o proxy do Vite cuida disso.

Para um app 100% standalone (sem abrir terminal), a próxima etapa é embutir o
backend como **sidecar**: gerar um `.exe` do backend com PyInstaller e declarar
esse binário em `tauri.conf.json` (`bundle.externalBin`), fazendo o Tauri
iniciá-lo junto com a janela. Isso ainda não está feito.

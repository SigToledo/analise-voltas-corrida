# Plano — App mobile (Android primeiro, iOS depois)

Decisões tomadas (05/07/2026):
- **Offline é obrigatório**: o app precisa analisar o PDF na pista, sem sinal.
- **Alvos**: Android e iPhone. **Ordem**: Android primeiro (APK direto, custo
  zero); iOS depois, pois exige Mac para compilar e conta Apple Developer
  (US$ 99/ano) para instalação prática fora da loja.
- **Distribuição**: uso próprio/equipe (sem lojas por enquanto).

## A decisão de arquitetura

O backend Python (FastAPI + pdfplumber) não roda em celular — o truque do
sidecar é exclusivo do desktop. Com offline obrigatório, a rota é **portar o
motor de análise para TypeScript**, rodando dentro do próprio app:

- Leitura do PDF com **pdf.js** (`pdfjs-dist`), que dá acesso ao texto com
  coordenadas — o mesmo insumo que o pdfplumber dá hoje.
- Parser e métricas reescritos em TS, reproduzindo as regras já validadas:
  falso negrito, colunas por posição X, leitura em serpentina, voltas de
  continuação, voltas-fantasma, voltas de pit ("p", inclusive o "p" separado
  do número), voltas de saída de box, corte do rodapé.
- Shell mobile com **Tauri 2** (mesmo framework do desktop, que já suporta
  Android/iOS), reaproveitando as telas React — já pensadas responsivas.

Bônus de longo prazo: com o motor em TS, o desktop pode um dia abandonar o
sidecar de 37 MB e virar um app único e menor.

## Rede de segurança do porte (o mais importante)

O parser é a parte mais delicada do projeto. O porte só é aceito quando
reproduzir EXATAMENTE o resultado do Python:

1. **Gabarito (golden files)**: rodar o backend Python nos PDFs reais de
   samples/ e congelar as saídas completas em JSON (parsing + métricas).
2. O motor TS é testado contra esses JSONs — qualquer diferença de um
   milésimo é reprovação.
3. A validação externa continua valendo: melhor volta 26/26 com o Best Tm
   oficial do cronômetro.

## Fases

- **M0 — Gabarito** ✅ decidido: gerar os golden files a partir do backend
  Python atual (script pequeno; os JSONs ficam fora do Git, junto de
  samples/, por conterem dados reais de treino).
- **M1 — Motor TS**: portar parser (Laptimes, detecção de tipo, resumo
  Qualify) e métricas; suíte de testes (vitest) contra o gabarito. Sem tela
  nova. É a fase mais longa.
- **M2 — App Android**: `tauri android init`; telas React atuais adaptadas
  para toque/tela estreita (chips, tabelas com scroll horizontal já
  previstos); seleção de arquivo pelo seletor do Android; gerar APK e
  instalar direto no aparelho.
- **M3 — Refinos de pista**: receber PDF via "Compartilhar" do WhatsApp/
  e-mail; histórico de sessões no aparelho; comparação entre sessões.
- **M4 — iOS** (quando houver Mac + conta Apple): mesmo código, build iOS
  via Tauri; distribuição por TestFlight.

## Pré-requisitos técnicos (Android, fase M2)

- Android Studio + SDK/NDK (instalação grande, ~10 GB).
- Rust targets Android (`rustup target add aarch64-linux-android` etc.).
- Java 17. Tudo em máquina Windows atual — sem custo.

## Riscos conhecidos

- **pdf.js vs pdfplumber**: as coordenadas/agrupamento de palavras não são
  idênticos; o tratamento do falso negrito e da tolerância vertical vai
  precisar de recalibração. O gabarito pega qualquer regressão.
- **iOS**: sem conta paga, instalação expira a cada 7 dias — por isso ficou
  por último.
- Celular de tela pequena: a tela "Onde ganhar tempo" precisará de revisão
  de usabilidade específica (heatmap em 360 px de largura).

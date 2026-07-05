# Plano — App mobile (PWA primeiro; nativo só se precisar)

Decisões tomadas (05/07/2026):
- **Offline é obrigatório**: o app precisa analisar o PDF na pista, sem sinal.
- **Aparelho principal: iPhone** (+ Androids da equipe).
- **Distribuição**: uso próprio/equipe (sem lojas).
- **Rota escolhida: PWA instalável.** App nativo iOS exigiria Mac para
  compilar e conta Apple Developer (US$ 99/ano) para não expirar em 7 dias —
  inviável para o caso de uso. O PWA instala pelo Safari ("Adicionar à Tela
  de Início"), funciona offline via service worker, roda igual no Android da
  equipe e custa zero. Limitações aceitas: sem "compartilhar direto do
  WhatsApp" no iOS (salva em Arquivos e abre no app) e o cache pode ser
  limpo pelo sistema após longa inatividade (basta reabrir com internet).

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

- **M0 — Gabarito**: gerar os golden files a partir do backend Python atual
  (script em backend/scripts/gerar_gabarito.py; os JSONs ficam em
  samples/gabarito/, fora do Git por conterem dados reais de treino).
- **M1 — Motor TS**: portar parser (Laptimes, detecção de tipo, resumo
  Qualify) e métricas; suíte de testes (vitest) contra o gabarito. Sem tela
  nova. É a fase mais longa.
- **M2 — PWA instalável**: manifest + service worker (vite-plugin-pwa) no
  frontend, análise 100% no aparelho (o PDF nunca sai do celular);
  hospedagem estática gratuita (Vercel/Netlify); instalar no iPhone pelo
  Safari e nos Androids da equipe pelo Chrome.
- **M3 — Refinos de pista**: histórico de sessões no aparelho (IndexedDB),
  usabilidade de toque, revisão do heatmap em tela estreita.
- **M4 — Nativo (opcional)**: Tauri iOS/Android, só se surgir necessidade
  real (ex.: compartilhar direto do WhatsApp). Exige Mac + conta Apple paga.

## Riscos conhecidos

- **pdf.js vs pdfplumber**: as coordenadas/agrupamento de palavras não são
  idênticos; o tratamento do falso negrito e da tolerância vertical vai
  precisar de recalibração. O gabarito pega qualquer regressão.
- **iOS**: sem conta paga, instalação expira a cada 7 dias — por isso ficou
  por último.
- Celular de tela pequena: a tela "Onde ganhar tempo" precisará de revisão
  de usabilidade específica (heatmap em 360 px de largura).

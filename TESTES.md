# Referência de testes

Rodar tudo: `python -m pytest` (≈ 12 s). O GitHub Actions roda a mesma suíte a cada push/PR. Nenhum teste acessa a internet: a API é
substituída por `FakeSource` (em `tests/conftest.py`) e por respostas reais
gravadas em out/2026. O teste da interface roda quando há display e é pulado
automaticamente em servidores sem tela.

Ao integrar uma funcionalidade nova, adicione os testes no arquivo do módulo
correspondente e atualize esta tabela.

| Arquivo | Módulo(s) | O que garante |
|---|---|---|
| `test_games_models.py` | `games`, `models`, `formatting` | Custo de apostas múltiplas em todas as loterias (inclui trevos), validação com mensagens amigáveis, Lotomania 00–99, aliases de nomes, sobrescrita de preços, parse de dezenas digitadas, formato R$ |
| `test_parsers_api.py` | `parsers`, `api_client` | Formato oficial e comunitário; separação dos 2 sorteios da Dupla Sena; trevos; Time do Coração e Mês da Sorte normalizados; respostas inválidas rejeitadas; fallback oficial → comunitária; histórico completo ignorando itens quebrados; erro quando todas as fontes falham |
| `test_storage_update.py` | `storage`, `migration`, `updater` | Ida e volta de todos os campos; upsert idempotente e cache invalidado; Meus jogos, bolões e meta; escrita concorrente (4 threads); migração do `megasena.db`/`user_sets.db` antigos (idempotente); sincronização em lote → incremental com progresso; fallback individual; offline com mensagem amigável; cancelamento |
| `test_analysis.py` | `stats`, `generator`, `checker`, `backtest` | Frequência e atraso; Dupla Sena conta os dois sorteios; p-valor do qui-quadrado (forma fechada e valor de referência); resumo de todas as loterias; todas as estratégias geram jogos válidos e únicos em todas as loterias; "mais sorteados" = top-N; reprodutibilidade por semente e diversidade; filtros "equilibrado" e "menos populares"; entradas inválidas; combinatória de apostas múltiplas (Mega 7 dezenas, Lotofácil 16–20); prêmio de 0 acertos na Lotomania; faixa do 2º sorteio na Dupla Sena; faixas com trevos na +Milionária; Mês da Sorte; backtest próximo da média do acaso; validação e cancelamento |
| `test_bolao_cli.py` | `bolao`, `export`, `cli`, `services` | Plano de orçamento; leitura de participantes (formatos e erros); criação, cota, rateio proporcional e texto de compartilhamento; serialização; CSVs; CLI ponta a ponta (atualizar, gerar, estatísticas, conferir, bolão, backtest, jogos), aviso de prêmio após `atualizar` e códigos de erro |
| `test_supersete_alerts.py` | `columns`, `game_spec`, `alerts`, `notifier` | Super Sete: leitura das duas APIs com dígitos repetidos, custo por coluna, entradas inválidas, combinatória por colunas (produto de polinômios), gerador com 1 a 3 números por coluna, bolão e CSV; avisos de jogo salvo e bolão premiados uma única vez por concurso; comandos de notificação seguros contra injeção (Windows/macOS/Linux) e falhas tratadas |
| `test_gui.py` | `gui.*` | Abre o app, sincroniza com API falsa (thread + fila), troca as 8 loterias, valida entrada inválida, gera, salva e confere jogos, monta e salva bolão, calcula estatísticas, exibe e fecha aviso de prêmio, abre a grade de colunas da Super Sete, alterna para o tema escuro e fecha liberando recursos |

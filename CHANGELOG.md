# Changelog

## [2.0.0] - 2026-10-19
Reescrita completa: o projeto deixa de ser só da Mega-Sena e vira **Loterias Estatístico**.

### Novidades
- 8 loterias: Mega-Sena, Lotofácil, Quina, Lotomania, Dupla Sena, Timemania, Dia de Sorte e +Milionária, com regras, preços (out/2026) e faixas de prêmio próprios.
- Atualização automática: ao abrir o app, a cada 30 min com ele aberto e por tarefa agendada no sistema (`main.py agendar`). Usa a API oficial da Caixa com a API comunitária como reserva e baixa o histórico completo numa requisição só.
- Bolão: orçamento → jogos diversificados, cotas, controle de pagamento, texto para WhatsApp, conferência e rateio do prêmio.
- Gerador com 6 estratégias (incluindo "Menos populares", que reduz a chance de dividir prêmio) e jogos diversificados.
- Conferência correta de apostas com mais dezenas (combinatória), com valores do rateio oficial.
- Backtest walk-forward comparando as estratégias com a média teórica do acaso.
- Interface nova em CustomTkinter, minimalista, com tema claro/escuro e cor de destaque por loteria.
- CLI com subcomandos (`atualizar`, `gerar`, `estatisticas`, `conferir`, `bolao`, `backtest`, `exportar`, `jogos`, `agendar`).

### Correções em relação à 1.4
- `init_db` retornava antes de criar a tabela, e `update_db`/`fetch_lottery_data`/`get_most_frequent` não existiam: `--update` não funcionava.
- `cli.py` só tinha comandos vazios (`pass`).
- A GUI alterava widgets a partir de threads de trabalho (instável no Tkinter). Agora tudo passa por uma fila na thread principal.
- `db_utils` usava `time`/`traceback` sem importar.

### Migração
- `megasena.db` e `user_sets.db` antigos são importados automaticamente para `data/loterias.db`.
- `python scripts/limpar_legado.py` move os arquivos da 1.x para `_legado/`.

## [1.4.0] - 2025-12-28
- Modularização inicial, gráficos na GUI, retry de banco.

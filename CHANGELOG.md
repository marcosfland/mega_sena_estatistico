# Changelog

## [2.2.0] - 2026-11-10

### Novidades
- **Instalador Windows** (Inno Setup, em português, sem pedir administrador) gerado pelo GitHub Actions a cada push na `main`, exceto quando só a base mudou. Vai para o pre-release "Última versão da main"; tags `v*` publicam o Release oficial.
- **Base de dados no GitHub:** `dados/<loteria>.jsonl` atualizado automaticamente duas vezes por dia pelo workflow *Atualizar base de dados*.
- O app usa essa base para começar com o histórico pronto (repositório e instalador) e como terceira fonte de dados pela internet, depois da API oficial e da comunitária.
- No executável instalado, banco, preferências e logs ficam em `%LOCALAPPDATA%\LoteriasEstatistico`.

### Alterações
- `release.yml` substituído por `instalador.yml`.

## [2.1.0] - 2026-11-10

### Novidades
- **Super Sete:** 9ª loteria, com modelo por colunas (códigos `coluna·dígito`). Inclui custo exato por coluna, conferência combinatória, gerador que sorteia dentro de cada coluna, grade de 7 linhas na aba Conferir e gráficos agrupados por coluna.
- **Avisos de prêmio:** jogos salvos e bolões são conferidos a cada concurso novo, com aviso no app e notificação nativa do sistema, também pela tarefa agendada. Pode ser desligado no interruptor *Avisar prêmios*.
- **GitHub Actions:** lint e testes a cada push/PR (Linux e Windows, Python 3.10 e 3.13). Uma tag `v*` gera o executável do Windows e publica o Release.
- `ruff.toml` com as regras de qualidade do projeto.

### Remoções
- Código da versão 1.x (`mega_sena_app.py`, `gui_main.py`, testes temporários, bancos antigos e documentos soltos) removido do repositório. O histórico continua no git.

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
- (2.1.0: os arquivos da 1.x foram removidos do repositório.)

## [1.4.0] - 2025-12-28
- Modularização inicial, gráficos na GUI, retry de banco.

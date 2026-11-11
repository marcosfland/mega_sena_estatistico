# Loterias Estatístico

[![Testes](https://github.com/marcosfland/mega_sena_estatistico/actions/workflows/testes.yml/badge.svg)](https://github.com/marcosfland/mega_sena_estatistico/actions/workflows/testes.yml)
[![Release](https://img.shields.io/github/v/release/marcosfland/mega_sena_estatistico?label=release)](https://github.com/marcosfland/mega_sena_estatistico/releases/latest)

Análise estatística, geração de jogos, conferência e **bolões** para as loterias da Caixa, com interface moderna (CustomTkinter, tema claro/escuro) e linha de comando.

| Loteria | Sorteio | Aposta | Preço mínimo |
|---|---|---|---|
| Mega-Sena | 6 de 01–60 | 6 a 20 | R$ 6,00 |
| Lotofácil | 15 de 01–25 | 15 a 20 | R$ 3,50 |
| Quina | 5 de 01–80 | 5 a 15 | R$ 3,00 |
| Lotomania | 20 de 00–99 | 50 | R$ 3,00 |
| Dupla Sena | 2 × 6 de 01–50 | 6 a 15 | R$ 3,00 |
| Timemania | 7 de 01–80 + time | 10 | R$ 3,50 |
| Dia de Sorte | 7 de 01–31 + mês | 7 a 15 | R$ 2,50 |
| +Milionária | 6 de 01–50 + 2 trevos de 1–6 | 6 a 12 (+2 a 6 trevos) | R$ 6,00 |
| Super Sete | 1 dígito (0–9) em cada uma das 7 colunas | 7 a 21 (1 a 3 por coluna) | R$ 3,00 |

Os preços podem ser ajustados em `data/settings.json` (`"prices": {"megasena": 6.0}`), caso a Caixa reajuste.

## Download (Windows)

Baixe o instalador `LoteriasEstatistico-Setup-<versão>.exe` e execute. Não precisa de Python nem de permissão de administrador.

- **[Versão estável](https://github.com/marcosfland/mega_sena_estatistico/releases/latest)**, publicada a cada tag `v*`;
- **[Última versão da main](https://github.com/marcosfland/mega_sena_estatistico/releases/tag/main-build)**, refeita automaticamente a cada alteração no código.

O instalador cria atalhos no menu Iniciar (e, se você quiser, na área de trabalho) e já traz a base de sorteios. Banco, preferências e logs ficam em `%LOCALAPPDATA%\LoteriasEstatistico` e são preservados ao atualizar ou desinstalar.

## Instalação pelo código

```bash
git clone https://github.com/marcosfland/mega_sena_estatistico.git
cd mega_sena_estatistico
pip install -r requirements.txt
python main.py
```

Requer Python 3.10 ou superior (testado em 3.10, 3.12 e 3.13, no Linux e no Windows). Na primeira abertura o app baixa o histórico de todas as loterias. A base antiga `megasena.db`, se existir, é importada sozinha.

## Atualização automática das bases

- **Com o app aberto:** verifica todas as loterias ao abrir e a cada 30 minutos (interruptor *Atualização automática* na barra lateral).
- **Com o app fechado:** `python main.py agendar --hora 21:30` cria uma tarefa diária no Agendador do Windows (no Linux/macOS mostra a linha do `crontab`). Para remover, use `python main.py agendar --remover`.
- **Avisos de prêmio:** quando sai um concurso novo, o app confere seus jogos salvos e bolões e mostra uma notificação do Windows (ou do macOS/Linux) se algum ganhou. Isso também vale para a tarefa agendada, com o app fechado. Para desligar, use o interruptor *Avisar prêmios*.
- **Fontes:** API oficial da Caixa (`servicebus2.caixa.gov.br`), depois a API comunitária `loteriascaixa-api` e, por último, a base deste repositório. Em base vazia, o histórico completo vem de uma vez, primeiro da base do repositório (um arquivo por loteria). Depois disso só os concursos novos são baixados, gravados em lotes.

## Base de dados no GitHub

A pasta [`dados/`](dados) guarda todos os concursos de cada loteria em `dados/<loteria>.jsonl`, com um concurso por linha. O workflow **Atualizar base de dados** roda todo dia às 22:30 e às 09:00 (horário de Brasília) e faz o seguinte:

1. carrega a base atual;
2. baixa só os concursos novos, da API oficial com a comunitária de reserva;
3. faz commit dos arquivos que mudaram, como `Atualiza base de dados: Mega-Sena 3072, Quina 6890`.

Cada execução mostra um resumo por loteria na aba *Actions*. Se todas as loterias falharem, a execução fica vermelha e o GitHub avisa por e-mail. Para forçar uma atualização, use *Run workflow* nessa mesma aba. Os commits da base **não** geram instalador novo.

Quem clona o repositório ou instala pelo instalador já começa com essa base, e o app também a usa como fonte de reserva pela internet.

## Interface

| Aba | O que faz |
|---|---|
| **Gerador** | Gera de 1 a 100 jogos com uma estratégia, mostra o custo e salva, copia ou exporta em CSV |
| **Estatísticas** | Gráficos de frequência, atraso, par/ímpar e soma, mais um painel com as dezenas mais e menos sorteadas, as atrasadas, as duplas e o teste qui-quadrado. Pode usar todo o histórico ou só os últimos 500, 100, 50 ou 20 concursos |
| **Conferir** | Grade clicável de dezenas (e trevos e mês, quando a loteria tem) para conferir qualquer concurso; *Meus jogos* confere os jogos salvos com o último resultado |
| **Bolão** | Recebe o orçamento e os participantes com suas cotas e monta o máximo de jogos diversificados. Calcula a cota, controla quem já pagou, gera o texto para o WhatsApp, confere o resultado e divide o prêmio |
| **Backtest** | Joga cada estratégia nos concursos passados, sem ver o futuro, e compara com a média do acaso |

## Estratégias do gerador

| Estratégia | Como escolhe |
|---|---|
| Mais sorteados | 1º jogo = dezenas mais frequentes da história (a ideia original do projeto); demais ponderados pela frequência |
| Quentes | Peso pela frequência nos últimos 50 concursos |
| Atrasados | Peso pelo tempo sem sair |
| Equilibrado | Aleatório, mas com soma e par/ímpar na faixa de 80% dos sorteios reais |
| Menos populares | Evita datas (1–31) e sequências, para reduzir a chance de **dividir** o prêmio |
| Aleatório puro | Referência (surpresinha) |

> **Importante:** num sorteio justo toda combinação tem a mesma chance. As estratégias mudam *quais* dezenas você escolhe, não a probabilidade de ganhar, e a aba Backtest mostra isso com dados reais. Jogue com responsabilidade.

Na **Super Sete**, a grade da aba Conferir tem uma linha por coluna. As dezenas aparecem como `coluna·dígito` (por exemplo, `3·8` é o 8 na 3ª coluna). Na linha de comando, digite coluna a coluna, separando dígitos da mesma coluna com `/`: `"5 3/8 7 1 4 0 6"`. As estratégias "Equilibrado" e "Menos populares" não se aplicam a ela.

Apostas com mais dezenas são conferidas corretamente. Por exemplo, um jogo de 7 dezenas com 6 acertos na Mega-Sena paga 1 Sena + 6 Quinas, com os valores do rateio oficial quando disponíveis.

## Linha de comando

```bash
python main.py jogos                                   # loterias e estado das bases
python main.py atualizar [-j lotofacil]                # atualiza todas ou uma
python main.py gerar -j megasena -e equilibrado -n 7 -q 5
python main.py estatisticas -j quina --ultimos 100
python main.py conferir -j megasena "05 12 23 34 45 56" [-c 3070]
python main.py conferir -j maismilionaria "1 2 3 4 5 6" -t "1 4"
python main.py conferir -j supersete "5 3/8 7 1 4 0 6"
python main.py bolao -j megasena --orcamento 300 -n 7 -p "Ana:2,Bruno,Carla:3" --salvar
python main.py backtest -j lotofacil --concursos 300
python main.py exportar -j quina historico_quina.csv
python main.py agendar --hora 21:30
```

## Estrutura

```
main.py                 entrada (sem argumentos = GUI; com argumentos = CLI)
loterias/
  games.py              catálogo: regras, preços e faixas de prêmio de cada loteria
  game_spec.py          classe GameSpec (custo, validação, formatação)
  columns.py            Super Sete: códigos coluna·dígito, custo e leitura por coluna
  models.py             Draw, Bet, PrizeTier
  storage.py            SQLite (sorteios, Meus jogos, bolões), modo WAL
  api_client.py         HTTP com fallback oficial → comunitária
  parsers.py            JSON das APIs → Draw
  updater.py            sincronização incremental / em lote
  migration.py          importa megasena.db e user_sets.db antigos
  stats.py              frequência, atraso, qui-quadrado, somas...
  generator.py          estratégias e diversificação de jogos
  checker.py            conferência com combinatória de apostas múltiplas
  backtest.py           backtest walk-forward
  bolao.py              cotas, orçamento, rateio, texto de compartilhamento
  dump.py               base versionada dados/*.jsonl (exportar, importar)
  alerts.py             avisos de prêmio de jogos salvos e bolões
  notifier.py           notificação nativa do sistema (Windows/macOS/Linux)
  cli.py · export.py · scheduler.py · services.py · settings.py · formatting.py
  gui/                  app, barra lateral, páginas, gráficos, widgets, avisos, runner de threads
tests/                  104 testes (pytest), ver TESTES.md
dados/                  base de sorteios versionada (atualizada pelo GitHub Actions)
scripts/atualizar_base.py  rotina de atualização da base (usada pelo workflow)
instalador/loterias.iss    script do instalador (Inno Setup)
.github/workflows/      testes.yml, instalador.yml e atualizar-base.yml
data/                   loterias.db e settings.json (criados automaticamente; no instalador,
                        ficam em %LOCALAPPDATA%\LoteriasEstatistico)
```

## Testes

```bash
python -m pytest
```

Veja [TESTES.md](TESTES.md) para o mapa completo do que cada teste cobre. A cada push ou pull request, o GitHub Actions roda o lint (`ruff check`, com as regras em `ruff.toml`) e os testes no Linux e no Windows, com Python 3.10 e 3.13.

## Instalador e versões

O workflow **Instalador** roda os testes, gera o executável com PyInstaller e monta o instalador com Inno Setup:

- **a cada push na `main`**, exceto quando só `dados/` mudou: atualiza o pre-release [Última versão da main](https://github.com/marcosfland/mega_sena_estatistico/releases/tag/main-build), com versão `2.2.0-build.<n>`;
- **a cada tag `v*`**: publica um Release oficial com o instalador e notas geradas a partir dos commits.

```bash
git tag v2.2.0
git push origin v2.2.0
```

O instalador também fica como artefato de cada execução. Para gerar só o executável localmente:

```bash
pip install pyinstaller
python build_executable.py      # gera dist/LoteriasEstatistico/
```

## Licença

MIT. Desenvolvido por [Marcos](https://github.com/marcosfland).

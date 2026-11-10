# Loterias Estatístico

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

Os preços podem ser ajustados em `data/settings.json` (`"prices": {"megasena": 6.0}`), caso a Caixa reajuste.

## Instalação

```bash
git clone https://github.com/marcosfland/mega_sena_estatistico.git
cd mega_sena_estatistico
pip install -r requirements.txt
python main.py
```

Requer Python 3.10 ou superior (testado em 3.12 e 3.13). Na primeira abertura o app baixa o histórico de todas as loterias. A base antiga `megasena.db`, se existir, é importada sozinha.

## Atualização automática das bases

- **Com o app aberto:** verifica todas as loterias ao abrir e a cada 30 minutos (interruptor *Atualização automática* na barra lateral).
- **Com o app fechado:** `python main.py agendar --hora 21:30` cria uma tarefa diária no Agendador do Windows (no Linux/macOS mostra a linha do `crontab`). Para remover, use `python main.py agendar --remover`.
- **Fontes:** API oficial da Caixa (`servicebus2.caixa.gov.br`), com a API comunitária `loteriascaixa-api` como reserva. Em base vazia, o histórico completo vem numa única requisição. Depois disso só os concursos novos são baixados, gravados em lotes.

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

Apostas com mais dezenas são conferidas corretamente. Por exemplo, um jogo de 7 dezenas com 6 acertos na Mega-Sena paga 1 Sena + 6 Quinas, com os valores do rateio oficial quando disponíveis.

## Linha de comando

```bash
python main.py jogos                                   # loterias e estado das bases
python main.py atualizar [-j lotofacil]                # atualiza todas ou uma
python main.py gerar -j megasena -e equilibrado -n 7 -q 5
python main.py estatisticas -j quina --ultimos 100
python main.py conferir -j megasena "05 12 23 34 45 56" [-c 3070]
python main.py conferir -j maismilionaria "1 2 3 4 5 6" -t "1 4"
python main.py bolao -j megasena --orcamento 300 -n 7 -p "Ana:2,Bruno,Carla:3" --salvar
python main.py backtest -j lotofacil --concursos 300
python main.py exportar -j quina historico_quina.csv
python main.py agendar --hora 21:30
```

## Estrutura

```
main.py                 entrada (sem argumentos = GUI; com argumentos = CLI)
loterias/
  games.py              regras, preços e faixas de prêmio de cada loteria
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
  cli.py · export.py · scheduler.py · services.py · settings.py · formatting.py
  gui/                  app, barra lateral, páginas, gráficos, widgets, runner de threads
tests/                  74 testes (pytest), ver TESTES.md
scripts/limpar_legado.py  move os arquivos da versão 1.x para _legado/
data/                   loterias.db e settings.json (criados automaticamente)
```

## Testes

```bash
python -m pytest
```

Veja [TESTES.md](TESTES.md) para o mapa completo do que cada teste cobre.

## Executável

```bash
pip install pyinstaller
python build_executable.py      # gera dist/LoteriasEstatistico/
```

## Licença

MIT. Desenvolvido por [Marcos](https://github.com/marcosfland).

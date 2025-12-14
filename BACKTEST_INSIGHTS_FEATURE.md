# 🎯 Recurso: Backtest Insights - Predição por Histórico de Acertos

## Descrição

O **Backtest Insights** é um novo método de geração de números que analisa o histórico de resultados dos backtests para identificar quais números foram **mais bem-sucedidos em acertar** durante as simulações retrospectivas.

Diferente de outros métodos que se baseiam apenas em frequência histórica, o Backtest Insights usa dados de **desempenho real** dos números durante backtests para criar predições mais precisas.

## 🔍 Como Funciona

1. **Análise de Backtests**: A função examina todos os resultados armazenados no banco de dados `backtest.db`
2. **Cálculo de Scores**: Cada número recebe um score baseado em quantos acertos teve durante os backtests
3. **Bônus de Performance**: Números que levaram a "Quadra" (4 acertos) ou mais recebem bônus exponencial
4. **Seleção de Top 6**: Os 6 números com maiores scores são retornados

### Fórmula de Score

```text
Para cada teste de backtest:
  - Se matches >= 4: score += matches²  (bônus exponencial)
  - Se matches < 4:  score += matches   (score linear)
```text

## 📊 Métodos Disponíveis

O Backtest Insights oferece 3 variações baseadas em diferentes métodos de backtest:

### `alltime`
- Usa dados de backtests baseados em frequência histórica total
- Reflete números com melhor performance ao longo de todo o histórico
- Comando: `--backtest-insights alltime`

### `lastyear`
- Usa dados de backtests baseados nos últimos 365 dias
- Reflete tendências mais recentes
- Comando: `--backtest-insights lastyear`

### `weighted`
- Usa dados de backtests baseados em ponderação estatística
- Combina histórico com análise de probabilidade
- Comando: `--backtest-insights weighted`

## 🚀 Como Usar

### Na Linha de Comando

```bash
# Gerar números usando backtest insights (weighted)
python mega_sena_app.py --backtest-insights weighted

# Usar método alltime
python mega_sena_app.py --backtest-insights alltime

# Usar método lastyear
python mega_sena_app.py --backtest-insights lastyear
```text

### Na Interface Gráfica

1. Clique no botão **"Backtest Insights"** na seção de Análises Estatísticas
2. Escolha o método desejado (alltime, lastyear ou weighted)
3. Os números gerados serão exibidos

### Ao Salvar Seus Números

1. Clique em **"Gerar Meus Números"**
2. Escolha o método: `backtest-insights`
3. Selecione qual método de backtest usar
4. Confirme e defina um nome para salvar o conjunto

## 📈 Exemplo de Saída

```text
Números gerados por insights de backtest (weighted): [21, 27, 28, 30, 44, 54]

Esses números foram selecionados com base no histórico de acertos dos backtests.
```text

## 🔄 Fluxo de Dados

```text
┌─────────────────────┐
│   Backtests         │
│  (alltime,          │
│   lastyear,         │
│   weighted)         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   backtest.db       │
│  (backtest_results) │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Análise de Scores   │
│ (matches por número)│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Ranking de Números  │
│   (Top 6 Seleitos)  │
└─────────────────────┘
```text

## ⚙️ Configuração Técnica

### Função Principal

```python
get_from_backtest_insights(method: str = "weighted", k: int = NUM_DEZENAS) -> List[int]
```text

**Parâmetros:**
- `method`: Qual método de backtest usar ('alltime', 'lastyear', 'weighted')
- `k`: Número de dezenas a gerar (padrão: 6)

**Retorno:**
- Lista de k números ordenados, baseados no desempenho histórico

### Banco de Dados

Usa a tabela `backtest_results` em `backtest.db`:
```sql
CREATE TABLE backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    method TEXT NOT NULL,
    date_tested TEXT NOT NULL,
    generated_numbers TEXT NOT NULL,  -- Números virgulados
    draw_date TEXT NOT NULL,
    matches INTEGER NOT NULL           -- Quantos números acertou (0-6)
)
```text

## 🎲 Casos de Uso

### 1. Validação de Estratégias
Use para identificar quais números consistentemente tiveram melhor desempenho nas suas estratégias de backtest.

### 2. Refinamento de Predições
Combine com outros métodos para criar conjuntos híbridos mais sofisticados.

### 3. Análise de Tendências
Monitore como os scores dos números variam ao longo do tempo conforme novos backtests são executados.

## ⚠️ Limitações

- **Dependência de Backtests**: Requer que backtests tenham sido executados previamente
- **Dados Históricos**: Quanto mais backtests, mais preciso o resultado
- **Bônus Exponencial**: Números com muitos acertos de "Quadra" ou mais podem dominar os resultados

## 🔧 Troubleshooting

### "Nenhum resultado de backtest encontrado"
- Execute um backtest primeiro: `python mega_sena_app.py --backtest-insights` (sem argumento, usa fallback)
- Ou manualmente via GUI: Clique em "Executar Backtest"

### Números iguais ao método "weighted"
- Normal quando não há dados suficientes de backtest
- Execute backtests para mais métodos para ver variação nos resultados

## 📊 Integração com Outros Recursos

O Backtest Insights funciona em conjunto com:
- **Conjuntos de Usuário**: Salve números gerados como conjuntos
- **Comparação**: Compare com últimos sorteios
- **Histórico**: Acompanhe o desempenho dos números gerados por backtest

## 📝 Próximas Melhorias

- [ ] Análise temporal de scores (ver evolução ao longo do tempo)
- [ ] Ponderação customizável de bônus exponencial
- [ ] Exportação de relatórios de backtest insights
- [ ] Machine learning para predição de scores futuros

---

**Versão**: 1.4.0  
**Data**: 2025-12-05  
**Status**: ✅ Pronto para Produção

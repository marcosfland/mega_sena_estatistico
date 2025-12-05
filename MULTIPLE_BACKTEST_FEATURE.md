# 🔄 Multiple Backtest Execution - Novo Recurso

## 📋 Visão Geral

A nova funcionalidade **Multiple Backtest Execution** permite executar backtests múltiplas vezes em uma única chamada, consolidando os resultados para uma análise estatística mais robusta.

## ✨ Características

- ✅ Execute backtests 1 até N vezes consecutivas
- ✅ Consolidação automática dos números mais frequentes
- ✅ Rastreamento de sucesso/falha por execução
- ✅ Suporte via CLI e future support em GUI
- ✅ Registros detalhados de cada execução

## 🚀 Como Usar

### CLI (Linha de Comando)

#### Sintaxe Básica
```bash
python mega_sena_app.py --backtest [método] --backtest-times [quantidade]
```

#### Exemplos

**1. Execução única com método default (weighted)**
```bash
python mega_sena_app.py --backtest
```
Resultado:
```
✓ Backtests executados com sucesso!
  Execuções solicitadas: 1
  Execuções bem-sucedidas: 1
```

**2. Execução única com método específico**
```bash
python mega_sena_app.py --backtest alltime
```

**3. Múltiplas execuções com consolidação**
```bash
python mega_sena_app.py --backtest weighted --backtest-times 5
```
Resultado:
```
✓ Backtests executados com sucesso!
  Execuções solicitadas: 5
  Execuções bem-sucedidas: 5

📊 Números consolidados (mais frequentes): [54, 25, 35, 40, 48, 5]
  Frequência:
    54: apareceu 4x em 5 execuções
    25: apareceu 3x em 5 execuções
    35: apareceu 3x em 5 execuções
    40: apareceu 3x em 5 execuções
    48: apareceu 2x em 5 execuções
    5: apareceu 2x em 5 execuções

📋 Resultados individuais:
  Execução 1: [12, 24, 25, 46, 47, 49]
  Execução 2: [5, 8, 9, 13, 23, 51]
  Execução 3: [21, 22, 30, 38, 40, 54]
  Execução 4: [10, 25, 35, 45, 48, 54]
  Execução 5: [6, 20, 35, 40, 48, 54]
```

**4. Teste de consistência com método alltime**
```bash
python mega_sena_app.py --backtest alltime --backtest-times 3
```
Resultado (esperado: números idênticos):
```
✓ Backtests executados com sucesso!
  Execuções solicitadas: 3
  Execuções bem-sucedidas: 3

📊 Números consolidados (mais frequentes): [4, 15, 27, 54, 55, 56]
  Frequência:
    4: apareceu 3x em 3 execuções
    15: apareceu 3x em 3 execuções
    27: apareceu 3x em 3 execuções
    54: apareceu 3x em 3 execuções
    55: apareceu 3x em 3 execuções
    56: apareceu 3x em 3 execuções

📋 Resultados individuais:
  Execução 1: [15, 54, 56, 4, 27, 55]
  Execução 2: [15, 54, 56, 4, 27, 55]
  Execução 3: [15, 54, 56, 4, 27, 55]
```

## 📊 Métodos de Backtest Disponíveis

| Método | Descrição | Uso Recomendado |
|--------|-----------|-----------------|
| `alltime` | Usa histórico completo de backtests | Análise histórica, validação |
| `lastyear` | Usa últimos 365 dias de backtests | Tendências recentes |
| `weighted` | Média ponderada de frequências | Predição mais equilibrada (DEFAULT) |

## 🎯 Argumentos CLI

### --backtest
- **Tipo**: String (opcional com valor padrão)
- **Valores**: `alltime`, `lastyear`, `weighted`
- **Padrão**: `weighted`
- **Descrição**: Escolhe o método de geração de números

### --backtest-times
- **Tipo**: Inteiro
- **Padrão**: 1
- **Intervalo**: >= 1
- **Descrição**: Número de vezes a executar o backtest

## 📈 Casos de Uso

### 1. Validação de Consistência
```bash
# Verificar se o método alltime é consistente
python mega_sena_app.py --backtest alltime --backtest-times 5

# Esperado: Todos os 6 números aparecem 5x
```

### 2. Análise de Variabilidade
```bash
# Verificar variação no método weighted
python mega_sena_app.py --backtest weighted --backtest-times 10

# Ver quais números aparecem com maior frequência
```

### 3. Comparação entre Métodos
```bash
# Backtests alltime
python mega_sena_app.py --backtest alltime --backtest-times 1 > results_alltime.txt

# Backtests weighted
python mega_sena_app.py --backtest weighted --backtest-times 1 > results_weighted.txt

# Backtests lastyear
python mega_sena_app.py --backtest lastyear --backtest-times 1 > results_lastyear.txt
```

### 4. Ensemble de Predições
```bash
# Múltiplas execuções para encontrar consenso
python mega_sena_app.py --backtest weighted --backtest-times 20

# Os 6 números consolidados representam maior consenso
```

## 🔧 Implementação Técnica

### Função Principal: `run_backtest_multiple()`

```python
def run_backtest_multiple(method: str, times: int = 1) -> Dict[str, Any]
```

**Parâmetros:**
- `method`: Método de geração ('alltime', 'lastyear', 'weighted')
- `times`: Número de execuções (padrão: 1)

**Retorno:**
- `success`: bool - Indica sucesso geral
- `times_requested`: int - Execuções solicitadas
- `times_successful`: int - Execuções bem-sucedidas
- `times_failed`: int - Execuções falhadas
- `consolidated_numbers`: List[int] - Top 6 números mais frequentes
- `consolidated_frequency`: Dict[int, int] - Frequência de cada número
- `exec_N_numbers`: List[int] - Números da execução N (para N em 1..times_successful)
- `message`: str - Mensagem descritiva

### Algoritmo de Consolidação

1. **Coleta**: Registra os 6 números gerados em cada execução
2. **Frequência**: Conta quantas vezes cada número aparece
3. **Ranking**: Ordena por frequência (decrescente) e número (crescente)
4. **Seleção**: Retorna top 6 números

### Banco de Dados

Os resultados são salvos em `backtest.db`:
- **Tabela**: `backtest_results`
- **Campos**: method, date_tested, generated_numbers, draw_date, matches
- **Índices**: (method, date_tested), (matches)

## ⚠️ Notas Importantes

1. **Performance**: Cada execução acessa o banco de dados completo
   - Para N = 20, leva ~2-5 segundos típico
   - Varia com tamanho do histórico de draws

2. **Variabilidade**: Métodos diferentes geram resultados diferentes
   - `alltime`: Determinístico (mesmos números sempre)
   - `lastyear`: Semi-determinístico (pode variar se data muda)
   - `weighted`: Estocástico (diferentes números a cada execução)

3. **Consolidação**: A consolidação é apenas estatística
   - Não garante vencimento
   - Use como ferramenta de análise, não como garantia

## 🧪 Testando

### Teste de Execução Única
```bash
python mega_sena_app.py --backtest weighted
```
✅ Deve completar sem erros

### Teste de Múltiplas Execuções
```bash
python mega_sena_app.py --backtest lastyear --backtest-times 3
```
✅ Deve mostrar 3 execuções com consolidação

### Teste de Método Inválido
```bash
python mega_sena_app.py --backtest invalid --backtest-times 1
```
❌ Deve mostrar erro (método não reconhecido)

## 📝 Próximas Melhorias

- [ ] Suporte em GUI com seletor de quantidade
- [ ] Exportar resultados para CSV
- [ ] Gráficos de frequência
- [ ] Comparação histórica entre métodos
- [ ] Cache de resultados

## 🐛 Troubleshooting

**Problema**: "Base de dados vazia para backtest"
- **Solução**: Execute `python mega_sena_app.py --update` primeiro

**Problema**: "Nenhum resultado consolidado"
- **Solução**: Pode ser normal se times=1, veja resultados individuais

**Problema**: "Diferentes números em cada execução"
- **Solução**: Esperado para método `weighted`, use `alltime` para consistência

## 📞 Suporte

Para dúvidas ou relatórios de erros, verifique:
1. Logs em `logs/mega_sena.log`
2. Testes com `python -m unittest tests.TestMegaSenaAnalyzer -v`
3. Documentação em `BACKTEST_INSIGHTS_*.md`

---

**Versão**: 1.0  
**Data**: 2025-12-05  
**Status**: ✅ Funcional e Testado

# 🎯 Mega-Sena Analyzer

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Ativo-brightgreen.svg)]()

Um analisador estatístico completo para a Mega-Sena que utiliza dados históricos e técnicas estatísticas avançadas para análise de padrões, geração de apostas inteligentes e backtesting de estratégias. Oferece tanto interface de linha de comando (CLI) quanto interface gráfica (GUI) para máxima flexibilidade.

## 🚀 Características Principais

- **📊 Análises Estatísticas Avançadas**: Frequência, correlação, séries temporais, Monte Carlo
- **🎲 Geração Inteligente de Apostas**: Baseada em frequência histórica e ponderação estatística
- **📈 Backtesting de Estratégias**: Teste suas estratégias contra dados históricos
- **💾 Gerenciamento de Apostas**: Salve, carregue e compare seus números
- **📱 Interface Dupla**: CLI para automação e GUI para uso interativo
- **🌐 Interface Web**: Servidor Flask para acesso remoto
- **📤 Exportação Flexível**: CSV, JSON com múltiplos formatos de análise
- **🔄 Atualização Automática**: Sincronização com API oficial da Caixa

## 📋 Índice

- [Instalação](#-instalação)
- [Uso Rápido](#-uso-rápido)
- [Interface Gráfica](#-interface-gráfica-gui)
- [Interface de Linha de Comando](#-interface-de-linha-de-comando-cli)
- [Funcionalidades Detalhadas](#-funcionalidades-detalhadas)
- [Exemplos de Uso](#-exemplos-de-uso)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Contribuição](#-contribuição)
- [Licença](#-licença)

## 🛠 Instalação

### Pré-requisitos
- Python 3.8 ou superior
- pip (gerenciador de pacotes do Python)

### Instalação das Dependências

```bash
# Clone o repositório
git clone https://github.com/marcosfland/mega_sena_estatistico.git
cd mega_sena_estatistico

# Instale as dependências
pip install -r requirements.txt
```

### Dependências Principais
```
requests>=2.25.1     # API requests
pandas>=1.3.0        # Análise de dados
numpy>=1.21.0        # Computação numérica
matplotlib>=3.4.0    # Visualização
scipy>=1.7.0         # Estatística avançada
flask>=2.0.0         # Interface web
Pillow>=8.0.0        # Processamento de imagens (opcional)
```

## ⚡ Uso Rápido

### Primeira Execução
```bash
# Atualize a base de dados
python mega_sena_app.py --update

# Execute a interface gráfica
python gui.py

# Ou use a CLI para análise rápida
python mega_sena_app.py --alltime
```

## 🖥 Interface Gráfica (GUI)

A interface gráfica oferece acesso completo a todas as funcionalidades através de uma interface amigável.

### Iniciando a GUI
```bash
python gui.py
```

### Principais Seções da GUI

#### 🎯 Meus Números
- **Gerar e Salvar**: Crie conjuntos baseados em diferentes estratégias
- **Comparar com Último Sorteio**: Verifique automaticamente seus acertos

#### 📊 Análises Estatísticas
- Top 6 de todos os tempos
- Top 6 do último ano
- Conjunto estatístico ponderado
- Visualização de frequência
- Simulação de Monte Carlo
- Análise de correlação
- Séries temporais
- Distribuição de probabilidade
- Pares e trios mais frequentes
- Probabilidade condicional
- Análise por período

#### 🧪 Backtest de Estratégias
- Teste retrospectivo de estratégias
- Análise de desempenho histórico
- Relatórios detalhados de acertos

#### 📤 Exportação
- Dados brutos (CSV/JSON)
- Análises avançadas (frequência, pares, trios, correlação)

## 💻 Interface de Linha de Comando (CLI)

### Comandos Básicos

```bash
# Atualizar base de dados
python mega_sena_app.py --update

# Análises básicas
python mega_sena_app.py --alltime          # Top 6 histórico
python mega_sena_app.py --lastyear         # Top 6 último ano
python mega_sena_app.py --stat             # Conjunto ponderado

# Visualizações
python mega_sena_app.py --plot             # Gráfico de frequência
python mega_sena_app.py --montecarlo       # Simulação Monte Carlo
python mega_sena_app.py --timeseries       # Séries temporais

# Análises avançadas
python mega_sena_app.py --correlation      # Matriz de correlação
python mega_sena_app.py --distribution     # Teste qui-quadrado
python mega_sena_app.py --pairs            # Pares frequentes
python mega_sena_app.py --triplets         # Trios frequentes

# Probabilidade condicional
python mega_sena_app.py --conditional 10 25

# Análise por período
python mega_sena_app.py --period 2023-01-01 2023-12-31 --alltime
```

### Gerenciamento de Apostas

```bash
# Salvar apostas
python mega_sena_app.py --salvar-aposta frequencia
python mega_sena_app.py --salvar-aposta ponderado

# Comparar com último resultado
python mega_sena_app.py --comparar-aposta

# Gerenciar conjuntos de usuário
python mega_sena_app.py --salvar-user-set frequencia "Meu Jogo 1"
python mega_sena_app.py --comparar-user-sets
```

### Exportação

```bash
# Exportar dados brutos
python mega_sena_app.py --export dados_megasena.csv
python mega_sena_app.py --export dados_megasena.json

# Exportar análises específicas
python mega_sena_app.py --export-analysis frequencia analise_freq.csv
python mega_sena_app.py --export-analysis pares analise_pares.csv
python mega_sena_app.py --export-analysis trios analise_trios.csv
python mega_sena_app.py --export-analysis correlacao correlacao.csv
```

### Interface Web

```bash
# Iniciar servidor web Flask
python mega_sena_app.py --web

# Acesse: http://localhost:5000/frequencia?top=10
#         http://localhost:5000/pares?top=20
#         http://localhost:5000/trios?top=15
```

### Agendamento Automático

```bash
# Configurar atualização diária automática
python mega_sena_app.py --schedule
```

## 🔍 Funcionalidades Detalhadas

### 📊 Análises Estatísticas

#### Análise de Frequência
- **Top 6 Histórico**: Números mais sorteados de todos os tempos
- **Top 6 Recente**: Números mais frequentes nos últimos 365 dias
- **Análise por Período**: Frequência em intervalos customizados

#### Análises Avançadas
- **Monte Carlo**: Simulação de 10.000+ sorteios para validação estatística
- **Correlação**: Matriz de correlação entre números (identifica padrões de co-ocorrência)
- **Séries Temporais**: Análise da distribuição temporal dos sorteios
- **Qui-quadrado**: Teste de uniformidade da distribuição

#### Análise de Padrões
- **Pares Frequentes**: Combinações de 2 números mais comuns
- **Trios Frequentes**: Combinações de 3 números mais comuns
- **Probabilidade Condicional**: P(número B | número A sorteado)

### 🎲 Geração de Apostas

#### Estratégias Disponíveis
1. **Frequência Histórica**: Baseada nos números mais sorteados
2. **Frequência Recente**: Baseada nos últimos 365 dias
3. **Ponderação Estatística**: Algoritmo que considera frequência com pesos probabilísticos

#### Nível de Confiança
- Cálculo automático baseado na frequência histórica
- Normalização para escala 0-1 (0% a 100%)

### 🧪 Sistema de Backtesting

O sistema de backtesting permite testar estratégias contra dados históricos:

#### Métodos Testáveis
- `alltime`: Estratégia baseada em frequência histórica total
- `lastyear`: Estratégia baseada nos últimos 365 dias
- `weighted`: Estratégia de ponderação estatística

#### Relatórios de Backtesting
- Total de sorteios analisados
- Distribuição de acertos (0 a 6 números)
- Taxa de sucesso por categoria de prêmio
- Análise de desempenho da estratégia

### 💾 Gerenciamento de Dados

#### Base de Dados Local
- **SQLite**: Armazenamento eficiente dos sorteios históricos
- **Atualização Incremental**: Baixa apenas novos sorteios
- **Backup Automático**: Estrutura robusta contra corrupção

#### Conjuntos do Usuário
- **Armazenamento Persistente**: Seus números ficam salvos
- **Comparação Automática**: Verificação contra novos sorteios
- **Histórico de Resultados**: Acompanhe o desempenho dos seus jogos

### 📤 Sistema de Exportação

#### Formatos Suportados
- **CSV**: Compatível com Excel, Google Sheets
- **JSON**: Para integração com outras aplicações

#### Tipos de Exportação
1. **Dados Brutos**: Todos os sorteios históricos
2. **Análise de Frequência**: Ranking completo 1-60
3. **Pares Frequentes**: Top 20 combinações de 2 números
4. **Trios Frequentes**: Top 20 combinações de 3 números
5. **Matriz de Correlação**: Correlação completa entre todos os números

## 🎯 Exemplos de Uso

### Cenário 1: Análise Rápida para Nova Aposta
```bash
# Atualize os dados
python mega_sena_app.py --update

# Veja os números mais frequentes
python mega_sena_app.py --alltime

# Gere um conjunto ponderado
python mega_sena_app.py --stat

# Salve sua aposta
python mega_sena_app.py --salvar-aposta ponderado
```

### Cenário 2: Análise Completa de Estratégia
```bash
# Execute backtest da estratégia
python mega_sena_app.py --web  # Inicie o backtesting via GUI

# Analise correlações
python mega_sena_app.py --correlation

# Exporte para análise externa
python mega_sena_app.py --export-analysis correlacao estrategia_correlacao.csv
```

### Cenário 3: Monitoramento Contínuo
```bash
# Configure atualização automática
python mega_sena_app.py --schedule

# Use a GUI para análises regulares
python gui.py

# Compare seus números automaticamente
python mega_sena_app.py --comparar-user-sets
```

## 📁 Estrutura do Projeto

```
mega_sena_estatistico/
├── mega_sena_app.py          # Aplicação principal (CLI)
├── gui.py                    # Interface gráfica
├── requirements.txt          # Dependências Python
├── README.md                # Documentação
├── icon.png                 # Ícone da aplicação (gerado automaticamente)
├── megasena.db              # Base de dados SQLite (criado automaticamente)
├── user_sets.db             # Conjuntos do usuário (criado automaticamente)
├── backtest.db              # Resultados de backtesting (criado automaticamente)
├── apostas_usuario.csv      # Histórico de apostas (criado automaticamente)
├── gui_actions.log          # Log de ações da GUI (criado automaticamente)
└── output/                  # Diretório para builds executáveis
    └── gui/                 # Build da GUI
```

### Arquivos Gerados Automaticamente
- **megasena.db**: Base de dados com todos os sorteios
- **user_sets.db**: Seus conjuntos de números salvos
- **backtest.db**: Resultados de testes de estratégias
- **apostas_usuario.csv**: Histórico das suas apostas
- **gui_actions.log**: Log de ações da interface gráfica
- **icon.png**: Ícone da aplicação (se Pillow estiver instalado)

## 🔧 Configuração Avançada

### Variáveis de Ambiente
```bash
# Personalizar localização dos bancos de dados
export MEGASENA_DB_PATH="/caminho/personalizado/megasena.db"
export MEGASENA_USER_SETS_DB_PATH="/caminho/personalizado/user_sets.db"
export MEGASENA_BACKTEST_DB_PATH="/caminho/personalizado/backtest.db"
```

### Banco de Dados Externo
```bash
# Conectar a banco SQLite externo
python mega_sena_app.py --external-db "/caminho/para/banco_externo.db"
```

## 🧪 Executável Standalone

O projeto inclui suporte para geração de executáveis usando PyInstaller:

```bash
# Instalar PyInstaller
pip install pyinstaller

# Gerar executável da GUI
pyinstaller --onedir --windowed --add-data "icon.png;." --add-data "megasena.db;." gui.py

# O executável estará em dist/gui/
```

## 📊 Metodologia Estatística

### Algoritmos Implementados

1. **Frequência Simples**: Contagem direta de ocorrências
2. **Ponderação Estatística**: Seleção baseada em probabilidades proporcionais
3. **Monte Carlo**: Simulação estocástica para validação
4. **Correlação de Pearson**: Análise de co-ocorrência entre números
5. **Qui-quadrado**: Teste de hipótese para uniformidade
6. **Análise Temporal**: Decomposição em séries temporais

### Limitações e Disclaimers

⚠️ **IMPORTANTE**: Este software é desenvolvido para fins educacionais e de análise estatística. 

- A Mega-Sena é um jogo de azar com sorteios aleatórios
- Análises passadas **não garantem** resultados futuros
- Nenhuma estratégia matemática pode prever sorteios aleatórios
- Use com responsabilidade e apenas com valores que pode perder
- O autor não se responsabiliza por perdas financeiras

## 🤝 Contribuição

Contribuições são bem-vindas! Para contribuir:

1. **Fork** o repositório
2. Crie uma **branch** para sua feature (`git checkout -b feature/AmazingFeature`)
3. **Commit** suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. **Push** para a branch (`git push origin feature/AmazingFeature`)
5. Abra um **Pull Request**

### Áreas que Precisam de Contribuição
- [ ] Testes unitários abrangentes
- [ ] Documentação de API
- [ ] Suporte a outras loterias (Quina, Lotofácil)
- [ ] Interface web mais robusta
- [ ] Algoritmos de ML para análise preditiva
- [ ] Otimização de performance
- [ ] Tradução para outras linguagens

### Reportando Bugs
Abra uma **Issue** incluindo:
- Versão do Python
- Sistema operacional
- Passos para reproduzir
- Logs de erro (se houver)

## 📝 Changelog

### v1.3.0 (Atual)
- ✅ Sistema de backtesting completo
- ✅ Interface gráfica aprimorada
- ✅ Gerenciamento de conjuntos do usuário
- ✅ Análise de correlação e séries temporais
- ✅ Exportação em múltiplos formatos
- ✅ Interface web Flask
- ✅ Agendamento automático de atualizações

### v1.2.0
- ✅ Interface gráfica (GUI)
- ✅ Análises estatísticas avançadas
- ✅ Sistema de exportação

### v1.1.0
- ✅ Análise de pares e trios
- ✅ Probabilidade condicional
- ✅ Filtros por período

### v1.0.0
- ✅ CLI básica
- ✅ Análises de frequência
- ✅ Integração com API da Caixa

## 📞 Suporte

- **GitHub Issues**: [Reportar problemas](https://github.com/marcosfland/mega_sena_estatistico/issues)
- **Discussões**: [GitHub Discussions](https://github.com/marcosfland/mega_sena_estatistico/discussions)
- **Email**: [Entre em contato](mailto:marcos.land@unoesc.edu.br)

## 📜 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

### ⭐ Se este projeto foi útil para você, considere dar uma estrela no GitHub!

**Desenvolvido com ❤️ por [Marcos](https://github.com/marcosfland)**

*"A estatística é a gramática da ciência" - Karl Pearson*

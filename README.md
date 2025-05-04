# mega_sena_estatistico

Um software que utiliza resultados passados da Mega-Sena e técnicas estatísticas para analisar padrões e selecionar números para futuras apostas. O objetivo é fornecer ferramentas analíticas e estatísticas para ajudar os usuários a entenderem melhor os sorteios e tomarem decisões informadas.

## Funcionalidades

### Atualização da Base de Dados
- **Descrição**: Atualiza a base de dados local com os resultados mais recentes da Mega-Sena utilizando uma API pública.
- **Uso**: `python mega_sena_app.py --update`

### Top 6 de Todos os Tempos
- **Descrição**: Exibe os 6 números mais frequentes em todos os sorteios registrados.
- **Uso**: `python mega_sena_app.py --alltime`

### Top 6 do Último Ano
- **Descrição**: Exibe os 6 números mais frequentes nos últimos 365 dias.
- **Uso**: `python mega_sena_app.py --lastyear`

### Conjunto Estatístico Ponderado
- **Descrição**: Calcula um conjunto de 6 números baseado em uma ponderação estatística dos sorteios passados.
- **Uso**: `python mega_sena_app.py --stat`

### Visualização de Frequência
- **Descrição**: Gera um gráfico de barras mostrando a frequência de cada número sorteado.
- **Uso**: `python mega_sena_app.py --plot`

### Simulação de Monte Carlo
- **Descrição**: Realiza uma simulação de Monte Carlo para estimar os números mais frequentes com base em sorteios simulados.
- **Uso**: `python mega_sena_app.py --montecarlo`

### Análise de Correlação
- **Descrição**: Calcula a matriz de correlação entre os números sorteados.
- **Uso**: `python mega_sena_app.py --correlation`

### Análise de Séries Temporais
- **Descrição**: Exibe a tendência de sorteios ao longo do tempo em um gráfico.
- **Uso**: `python mega_sena_app.py --timeseries`

### Análise de Distribuição de Probabilidade
- **Descrição**: Realiza um teste qui-quadrado para verificar a uniformidade da distribuição dos números sorteados.
- **Uso**: `python mega_sena_app.py --distribution`

### Exportação de Resultados
- **Descrição**: Exporta os resultados das análises para arquivos nos formatos CSV ou JSON.
- **Uso**: `python mega_sena_app.py --export <nome_do_arquivo>.<formato>`

### Interface Gráfica (GUI)
- **Descrição**: Uma interface gráfica simples para acessar as principais funcionalidades do programa.
- **Uso**: Execute o arquivo `gui.py` com o comando `python gui.py`.

## Requisitos
Certifique-se de instalar todas as dependências listadas no arquivo `requirements.txt` antes de executar o programa:
```bash
pip install -r [requirements.txt](http://_vscodecontentref_/0)

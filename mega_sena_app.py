#!/usr/bin/env python3
"""
Mega-Sena Analyzer

Este script cria/atualiza a base de dados local (SQLite) com resultados da Mega-Sena via API pública,
calcula os 6 números mais frequentes de todos os tempos, dos últimos 365 dias e um conjunto estatístico
ponderado, e oferece diversas funcionalidades de análise e exportação.

Dependências:
    pip install requests pandas numpy matplotlib Flask

Uso:
    python mega_sena_app.py --update             # Atualiza a base de dados local
    python mega_sena_app.py --alltime            # Exibe top 6 de todos os tempos
    python mega_sena_app.py --lastyear           # Exibe top 6 do último ano
    python mega_sena_app.py --stat               # Exibe conjunto estatístico ponderado
    python mega_sena_app.py --plot               # Visualiza a frequência dos números
    python mega_sena_app.py --pairs              # Exibe pares de números mais frequentes
    python mega_sena_app.py --web                # Inicia a interface web Flask
    python mega_sena_app.py --export-advanced frequencia resultados # Exporta frequência para CSV
    python mega_sena_app.py --schedule           # Agenda atualização diária
"""

import argparse
import datetime
import os
import sqlite3
import random
import logging
import json
import csv
import subprocess
import re
import functools
import hashlib
from collections import Counter
from itertools import combinations
from typing import List, Tuple, Dict, Any, Optional

# Importar sistema de configuração e logs
CONFIG_AVAILABLE = False
get_config = None
get_db_path = None
get_monte_carlo_simulations = None
is_cache_enabled = None
setup_enhanced_logging = None
get_logger = None
log_performance = None
log_analysis_result = None

try:
    from config import get_config, get_db_path, get_monte_carlo_simulations, is_cache_enabled
    from logging_config import setup_enhanced_logging, get_logger, log_performance, log_analysis_result
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    logging.warning("Sistema de configuração não disponível. Usando valores padrão.")

# Conditional imports for external libraries
# These are placed here to indicate they are optional if only core functionality is used.
try:
    import requests
except ImportError:
    print("Por favor, instale a biblioteca 'requests': pip install requests")
    exit(1)

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from scipy.stats import chisquare
except ImportError:
    logging.warning("Bibliotecas de análise (matplotlib, numpy, pandas, scipy) não encontradas. Algumas funcionalidades podem não estar disponíveis.")
    plt = None
    np = None
    pd = None
    chisquare = None

try:
    from flask import Flask, jsonify, request
except ImportError:
    logging.warning("Biblioteca 'Flask' não encontrada. A interface web não estará disponível.")
    Flask = None
    jsonify = None
    request = None


# Configurações
if CONFIG_AVAILABLE and get_config and get_db_path:
    try:
        config = get_config()
        DB_PATH: str = os.getenv('MEGASENA_DB_PATH', get_db_path())
    except (NameError, AttributeError) as e:
        logging.warning(f"Erro ao obter configuração: {e}. Usando valores padrão.")
        config = None
        DB_PATH: str = os.getenv('MEGASENA_DB_PATH', 'megasena.db')
    except Exception as e:
        logging.warning(f"Erro ao obter configuração: {e}. Usando valores padrão.")
        config = None
        DB_PATH: str = os.getenv('MEGASENA_DB_PATH', 'megasena.db')
else:
    config = None
    DB_PATH: str = os.getenv('MEGASENA_DB_PATH', 'megasena.db')

API_BASE: str = 'https://loteriascaixa-api.herokuapp.com/api/megasena'
USER_SETS_DB_PATH: str = os.getenv('MEGASENA_USER_SETS_DB_PATH', 'user_sets.db')
BACKTEST_DB_PATH: str = os.getenv('MEGASENA_BACKTEST_DB_PATH', 'backtest.db')

# Constants
NUM_DEZENAS: int = 6
MAX_NUM_MEGA_SENA: int = 60

# Configuração de logging
if CONFIG_AVAILABLE and setup_enhanced_logging:
    try:
        logger = setup_enhanced_logging()
    except (NameError, AttributeError):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        logger = logging.getLogger('mega_sena')
else:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger('mega_sena')

# Type alias for better readability
Draw = Tuple[datetime.date, Tuple[int, int, int, int, int, int]]

# Cache para melhorar performance
_draws_cache = None
_cache_hash = None

def get_db_hash(path: str = DB_PATH) -> str:
    """Gera hash do arquivo de banco para invalidar cache quando necessário"""
    try:
        with open(path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except (FileNotFoundError, IOError):
        return "no_db"

def invalidate_cache():
    """Invalida o cache de draws"""
    global _draws_cache, _cache_hash
    _draws_cache = None
    _cache_hash = None


# --- Banco de Dados ---
def init_db(path: str = DB_PATH) -> None:
    """
    Inicializa a base de dados SQLite, criando a tabela megasena se não existir.
    Adiciona índices para melhor performance.
    """
    try:
        with sqlite3.connect(path, timeout=20.0) as conn:
            conn.execute('PRAGMA journal_mode=WAL')  # Write-Ahead Logging reduz locks
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS megasena (
                    concurso INTEGER PRIMARY KEY,
                    data TEXT,
                    dez1 INTEGER, dez2 INTEGER, dez3 INTEGER,
                    dez4 INTEGER, dez5 INTEGER, dez6 INTEGER
                )
            ''')
            
            # Adicionar índices para consultas frequentes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_data ON megasena(data)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_concurso ON megasena(concurso)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_numeros ON megasena(dez1, dez2, dez3, dez4, dez5, dez6)')
            
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Erro ao inicializar o banco de dados: {e}")

def get_last_db_concurso(path: str = DB_PATH) -> int:
    """
    Retorna o número do último concurso registrado no banco de dados.
    Retorna 0 se o banco de dados estiver vazio ou houver um erro.
    """
    try:
        with sqlite3.connect(path, timeout=20.0) as conn:
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute('SELECT MAX(concurso) FROM megasena')
            row = cursor.fetchone()
            return row[0] or 0
    except sqlite3.Error as e:
        logging.error(f"Erro ao obter o último concurso do banco de dados: {e}")
        return 0

# --- API Integration ---
API_LOTERIAS: Dict[str, str] = {
    "megasena": "https://loteriascaixa-api.herokuapp.com/api/megasena",
    "quina": "https://loteriascaixa-api.herokuapp.com/api/quina",
    "lotofacil": "https://loteriascaixa-api.herokuapp.com/api/lotofacil"
}

def fetch_lottery_data(lottery: str = "megasena", concurso: Optional[int] = None) -> Dict[str, Any]:
    """
    Busca dados de um concurso específico de uma loteria na API.
    Se 'concurso' for None, busca o último resultado.
    """
    if lottery not in API_LOTERIAS:
        raise ValueError(f"Loteria '{lottery}' não suportada.")

    url: str = f"{API_LOTERIAS[lottery]}/{concurso}" if concurso else f"{API_LOTERIAS[lottery]}/latest"
    try:
        resp: requests.Response = requests.get(url)
        resp.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        data: Dict[str, Any] = resp.json()
        if not validate_api_data(data, lottery):
            raise ValueError(f"Dados inválidos recebidos para o concurso {concurso} da {lottery}.")
        return data
    except requests.RequestException as e:
        logging.error(f"Erro ao buscar dados da API para {lottery} (Concurso: {concurso if concurso else 'latest'}): {e}")
        raise
    except ValueError as e:
        logging.error(e)
        raise

def validate_api_data(data: Dict[str, Any], lottery: str) -> bool:
    """
    Valida os dados retornados pela API para a loteria especificada.
    """
    if lottery == "megasena":
        required_keys = {'concurso', 'data', 'dezenas'}
        if not all(key in data for key in required_keys):
            logging.warning(f"Dados da API para Mega-Sena faltando chaves esperadas: {data.keys()}")
            return False
        if not isinstance(data['dezenas'], list) or len(data['dezenas']) != NUM_DEZENAS:
            logging.warning(f"Dezenas inválidas para Mega-Sena: {data.get('dezenas')}")
            return False
    # Adicionar validações para outras loterias se necessário
    # elif lottery == "quina":
    #     ...
    return True

# --- Atualização de Dados ---
def update_db(path: str = DB_PATH) -> None:
    """
    Atualiza a base de dados local com os resultados mais recentes da Mega-Sena.
    """
    init_db(path)
    ultimo_db: int = get_last_db_concurso(path)
    ultimo_api: int = 0

    try:
        data_last: Dict[str, Any] = fetch_lottery_data("megasena", None)
        ultimo_api = int(data_last['concurso'])
    except Exception as e:
        logging.error(f"Erro ao obter o último concurso da API: {e}")
        return

    if ultimo_api <= ultimo_db:
        logging.info(f"Base já está atualizada até o concurso {ultimo_db}")
        return

    try:
        with sqlite3.connect(path, timeout=20.0) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            cursor: sqlite3.Cursor = conn.cursor()

            for concurso in range(ultimo_db + 1, ultimo_api + 1):
                try:
                    jogo: Dict[str, Any] = fetch_lottery_data("megasena", concurso)
                    dezenas: List[int] = sorted(list(map(int, jogo['dezenas']))) # Always store sorted
                    cursor.execute('''
                        INSERT OR IGNORE INTO megasena
                        (concurso, data, dez1, dez2, dez3, dez4, dez5, dez6)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (concurso, jogo['data'], *dezenas))
                    logging.info(f"Inserido concurso {concurso}")
                except Exception as e:
                    logging.warning(f"Concurso {concurso} indisponível ou inválido: {e}")
                    # Don't break the loop, try next contest
                    continue
            conn.commit()
            logging.info(f"Atualização concluída até o concurso {ultimo_api}")
            # Invalidar cache após atualização
            invalidate_cache()
    except sqlite3.Error as e:
        logging.error(f"Erro ao inserir dados no banco de dados: {e}")

# --- Cálculos Estatísticos ---
def load_all_draws(path: str = DB_PATH) -> List[Draw]:
    """
    Carrega todos os sorteios da Mega-Sena do banco de dados com cache.
    Retorna uma lista de tuplas (data, dezenas).
    """
    global _draws_cache, _cache_hash
    
    # Verificar se o cache ainda é válido
    current_hash = get_db_hash(path)
    if _draws_cache is not None and _cache_hash == current_hash:
        return _draws_cache
    
    draws: List[Draw] = []
    try:
        with sqlite3.connect(path, timeout=20.0) as conn:
            conn.execute('PRAGMA query_only = ON')  # Modo read-only
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute('SELECT data, dez1, dez2, dez3, dez4, dez5, dez6 FROM megasena ORDER BY concurso ASC')
            rows = cursor.fetchall()
            for data_str, *dez in rows:
                try:
                    date = datetime.datetime.strptime(data_str, '%d/%m/%Y').date()
                    draws.append((date, tuple(sorted(dez)))) # Ensure dezenas are sorted
                except ValueError as e:
                    logging.warning(f"Erro ao parsear data '{data_str}' ou dezenas '{dez}': {e}. Pulando registro.")
                    continue
            
            # Atualizar cache
            _draws_cache = draws
            _cache_hash = current_hash
            logging.info(f"Cache de draws atualizado. {len(draws)} sorteios carregados.")
            
    except sqlite3.Error as e:
        logging.error(f"Erro ao carregar sorteios do banco de dados: {e}")
    return draws

def get_most_frequent(draws: List[Draw], k: int = NUM_DEZENAS) -> List[int]:
    """
    Calcula os k números mais frequentes em todos os sorteios.
    """
    counter: Counter = Counter()
    for _, nums in draws:
        counter.update(nums)
    return [num for num, _ in counter.most_common(k)]

def get_most_frequent_period(draws: List[Draw], days: int = 365, k: int = NUM_DEZENAS) -> List[int]:
    """
    Calcula os k números mais frequentes em um período específico (em dias).
    """
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=days)
    filtered = [(d, nums) for d, nums in draws if d >= cutoff]
    if not filtered:
        logging.warning(f"Nenhum sorteio encontrado nos últimos {days} dias.")
        return []
    return get_most_frequent(filtered, k)

def get_weighted(draws: List[Draw], k: int = NUM_DEZENAS) -> List[int]:
    """
    Gera um conjunto de números ponderado pela frequência histórica.
    """
    counter: Counter = Counter()
    for _, nums in draws:
        counter.update(nums)
    all_nums: List[int] = list(range(1, MAX_NUM_MEGA_SENA + 1))
    weights: List[int] = [counter[n] for n in all_nums]

    if sum(weights) == 0:
        logging.warning("Não há dados de frequência para ponderar, gerando números aleatórios.")
        return sorted(random.sample(all_nums, k))

    # Normalize weights to probabilities
    total_weights: int = sum(weights)
    probs: List[float] = [w / total_weights for w in weights]

    chosen: set[int] = set()
    while len(chosen) < k:
        picks = random.choices(all_nums, weights=probs, k=k - len(chosen))
        chosen.update(picks)
    return sorted(list(chosen)) # Convert set to list and sort

def get_from_backtest_insights(method: str = "weighted", k: int = NUM_DEZENAS) -> List[int]:
    """
    Gera um conjunto de números baseado na análise de resultados de backtest.
    Utiliza os dados históricos de quais números foram mais bem-sucedidos
    em acertar durante os backtests.
    
    Args:
        method: Qual método de backtest usar ('alltime', 'lastyear', 'weighted')
        k: Número de dezenas a gerar (padrão 6)
    
    Returns:
        Lista de k números ordenados, baseados no desempenho histórico
    """
    try:
        init_backtest_db()
        all_nums: List[int] = list(range(1, MAX_NUM_MEGA_SENA + 1))
        number_scores: Dict[int, float] = {n: 0.0 for n in all_nums}
        
        with sqlite3.connect(BACKTEST_DB_PATH, timeout=20.0) as conn:
            cursor: sqlite3.Cursor = conn.cursor()
            
            # Buscar todos os backtest results para o método especificado
            cursor.execute('''
                SELECT generated_numbers, matches
                FROM backtest_results
                WHERE method = ?
            ''', (method,))
            
            results = cursor.fetchall()
            
            if not results:
                logging.warning(f"Nenhum resultado de backtest encontrado para o método '{method}'. Usando método ponderado.")
                draws = load_all_draws()
                return get_weighted(draws, k) if draws else sorted(random.sample(all_nums, k))
            
            # Analisar cada resultado de backtest
            for generated_numbers_str, matches in results:
                try:
                    generated_numbers = [int(n) for n in generated_numbers_str.split(',')]
                    
                    # Cada número que apareceu neste backtest recebe um score baseado em matches
                    # Números que levaram a mais acertos recebem scores maiores
                    for num in generated_numbers:
                        if num in number_scores:
                            # Score = quantidade de acertos, com bônus exponencial para acertos maiores
                            if matches >= 4:  # Quadra ou mais
                                number_scores[num] += (matches ** 2)  # Bônus exponencial
                            else:
                                number_scores[num] += matches
                
                except (ValueError, IndexError):
                    logging.warning(f"Erro ao processar resultado de backtest: {generated_numbers_str}")
                    continue
        
        # Se todos os scores são zero, usar método ponderado como fallback
        if sum(number_scores.values()) == 0:
            logging.info("Nenhum acerto histórico encontrado no backtest. Usando método ponderado como fallback.")
            draws = load_all_draws()
            return get_weighted(draws, k) if draws else sorted(random.sample(all_nums, k))
        
        # Selecionar os k números com maiores scores
        sorted_numbers = sorted(number_scores.items(), key=lambda x: x[1], reverse=True)
        top_numbers = [num for num, score in sorted_numbers[:k]]
        
        logging.info(f"Números gerados usando insights de backtest ({method}): {sorted(top_numbers)}")
        logging.debug(f"Scores: {[(num, number_scores[num]) for num in sorted(top_numbers)]}")
        
        return sorted(top_numbers)
        
    except Exception as e:
        logging.error(f"Erro ao gerar números a partir de backtest insights: {e}")
        # Fallback para weighted
        draws = load_all_draws()
        return get_weighted(draws, k) if draws else sorted(random.sample(list(range(1, MAX_NUM_MEGA_SENA + 1)), k))

def plot_frequency(draws: List[Draw]) -> None:
    """
    Gera um gráfico de barras da frequência de cada número sorteado.
    """
    if not plt:
        logging.error("Matplotlib não está instalado. Não é possível gerar o gráfico de frequência.")
        return

    counter: Counter = Counter()
    for _, nums in draws:
        counter.update(nums)

    # Ensure all numbers from 1 to MAX_NUM_MEGA_SENA are in the counter, even if frequency is 0
    full_data = {i: counter[i] for i in range(1, MAX_NUM_MEGA_SENA + 1)}
    numbers = list(full_data.keys())
    frequencies = list(full_data.values())

    plt.figure(figsize=(12, 6))
    plt.bar(numbers, frequencies, color='skyblue')
    plt.title('Frequência dos Números Sorteados na Mega-Sena')
    plt.xlabel('Número')
    plt.ylabel('Frequência')
    plt.xticks(range(1, MAX_NUM_MEGA_SENA + 1, 5)) # Show ticks every 5 numbers
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.show()

def monte_carlo_simulation(draws: List[Draw], simulations: Optional[int] = None) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """
    Realiza uma simulação de Monte Carlo para comparar frequências simuladas com as reais.
    Retorna os 6 números mais frequentes simulados e reais.
    """
    if not np:
        logging.error("NumPy não está instalado. Não é possível realizar a simulação de Monte Carlo.")
        return [], []

    # Usar configuração se disponível
    if simulations is None:
        try:
            if CONFIG_AVAILABLE and get_monte_carlo_simulations:
                simulations = get_monte_carlo_simulations()
            else:
                simulations = 10000
        except (NameError, AttributeError):
            simulations = 10000

    all_nums: List[int] = list(range(1, MAX_NUM_MEGA_SENA + 1))
    simulated_counts: Counter = Counter()

    # Log início da simulação
    start_time = datetime.datetime.now()

    for _ in range(simulations):
        # Simulate a draw of 6 unique numbers
        simulated_draw = np.random.choice(all_nums, size=NUM_DEZENAS, replace=False)
        simulated_counts.update(simulated_draw)

    real_counts: Counter = Counter()
    for _, nums in draws:
        real_counts.update(nums)
        
    most_simulated: List[Tuple[int, int]] = simulated_counts.most_common(NUM_DEZENAS)
    most_real: List[Tuple[int, int]] = real_counts.most_common(NUM_DEZENAS)
    
    # Log resultado
    if CONFIG_AVAILABLE and log_performance and log_analysis_result:
        duration = (datetime.datetime.now() - start_time).total_seconds()
        try:
            log_performance('monte_carlo_simulation', duration, f"{simulations} simulações")
            log_analysis_result('Monte Carlo', len(most_simulated), duration)
        except (NameError, TypeError):
            # Funções de log não disponíveis
            pass
    
    return most_simulated, most_real

def calculate_correlation(draws: List[Draw]) -> Optional[Any]:
    """
    Calcula a matriz de correlação entre os números sorteados.
    """
    if pd is None:
        logging.error("Pandas não está instalado. Não é possível calcular a correlação.")
        return None

    data: List[List[int]] = []
    for _, nums in draws:
        # Create a binary array for each draw: 1 if number is present, 0 otherwise
        draw_binary: List[int] = [1 if i in nums else 0 for i in range(1, MAX_NUM_MEGA_SENA + 1)]
        data.append(draw_binary)

    if not data:
        logging.warning("Não há dados de sorteios para calcular a correlação.")
        return None

    df = pd.DataFrame(data, columns=[f'Num_{i}' for i in range(1, MAX_NUM_MEGA_SENA + 1)])
    correlation_matrix = df.corr()
    return correlation_matrix

def analyze_probability_distribution(draws: List[Draw]) -> Optional[Tuple[float, float]]:
    """
    Analisa a distribuição de probabilidade dos números sorteados usando o teste Qui-quadrado.
    Compara a frequência observada com uma distribuição uniforme esperada.
    """
    if not chisquare:
        logging.error("SciPy não está instalado. Não é possível realizar a análise de distribuição de probabilidade.")
        return None

    counter: Counter = Counter()
    for _, nums in draws:
        counter.update(nums)

    # Ensure all numbers from 1 to MAX_NUM_MEGA_SENA are included, even if they have 0 frequency
    observed: List[int] = [counter[i] for i in range(1, MAX_NUM_MEGA_SENA + 1)]

    if sum(observed) == 0:
        logging.warning("Não há dados de sorteios para analisar a distribuição de probabilidade.")
        return None

    # Expected frequency for a uniform distribution
    expected: List[float] = [sum(observed) / MAX_NUM_MEGA_SENA] * MAX_NUM_MEGA_SENA

    chi2, p = chisquare(observed, expected)
    return chi2, p

def analyze_time_series(draws: List[Draw]) -> None:
    """
    Analisa a série temporal dos sorteios, mostrando a frequência de sorteios ao longo do tempo.
    """
    if not plt:
        logging.error("Matplotlib não está instalado. Não é possível gerar o gráfico de séries temporais.")
        return

    # Extract dates and count occurrences for each date
    date_counts: Counter = Counter(d for d, _ in draws)

    # Sort dates and get corresponding counts
    sorted_dates: List[datetime.date] = sorted(date_counts.keys())
    counts: List[int] = [date_counts[date] for date in sorted_dates]

    if not sorted_dates:
        logging.warning("Não há dados de sorteios para analisar a série temporal.")
        return

    plt.figure(figsize=(12, 6))
    # Convert dates to matplotlib date numbers for plotting
    import matplotlib.dates as mdates
    sorted_dates_num = mdates.date2num(sorted_dates)
    plt.plot_date(sorted_dates_num, counts, marker='o', linestyle='-', markersize=4, color='orange')
    plt.title('Frequência de Sorteios da Mega-Sena ao Longo do Tempo')
    plt.xlabel('Data do Sorteio')
    plt.ylabel('Número de Sorteios no Dia (deveria ser 1 para cada concurso)')
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.gcf().autofmt_xdate()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def sanitize_filename(filename: str) -> str:
    """
    Sanitiza um nome de arquivo para evitar path traversal e caracteres inválidos.
    Permite apenas letras, números, underline, hífen, ponto e espaço.
    """
    # Remove leading/trailing whitespace
    filename = filename.strip()
    # Replace any sequence of invalid characters with an underscore
    filename = re.sub(r'[^\w\-. ]', '_', filename)
    # Ensure it's not empty after sanitization
    if not filename:
        raise ValueError("Nome de arquivo resultante vazio após sanitização.")
    return filename

def export_results(data: List[Tuple[Any, Any]], file_format: str = "csv", filename: str = "results", header: Optional[List[str]] = None) -> None:
    """
    Exporta resultados para CSV ou JSON.
    É uma função mais genérica para a exportação de listas de tuplas/listas.
    """
    full_filename: Optional[str] = None
    try:
        filename = sanitize_filename(filename)
        full_filename = f"{filename}.{file_format}"
        if file_format == "csv":
            with open(full_filename, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                if header:
                    writer.writerow(header)
                writer.writerows(data)
        elif file_format == "json":
            # For JSON, if data is a list of tuples, convert to list of lists or dicts
            json_data = [list(item) for item in data] if isinstance(data[0], tuple) else data
            with open(full_filename, "w", encoding="utf-8") as jsonfile:
                json.dump(json_data, jsonfile, indent=4, ensure_ascii=False)
        else:
            logging.error(f"Formato de arquivo '{file_format}' não suportado para exportação.")
            return
        logging.info(f"Resultados exportados para {full_filename}")
    except ValueError as e:
        logging.error(f"Erro ao sanitizar nome do arquivo: {e}")
    except IOError as e:
        if full_filename:
            logging.error(f"Erro de I/O ao exportar resultados para '{full_filename}': {e}")
        else:
            logging.error(f"Erro de I/O ao exportar resultados: {e}")
    except Exception as e:
        logging.error(f"Erro inesperado ao exportar resultados: {e}")

def schedule_task_crossplatform() -> None:
    """
    Agenda a atualização diária do banco de dados de forma multiplataforma.
    Usa `schtasks` no Windows e fornece instrução para `crontab` em Linux/macOS.
    """
    import platform
    task_name: str = "MegaSenaUpdate"
    script_path: str = os.path.abspath(__file__)

    if platform.system() == "Windows":
        command: str = f"schtasks /create /tn \"{task_name}\" /tr \"cmd /c python {script_path} --update\" /sc daily /st 12:00 /F"
        logging.info(f"Tentando agendar tarefa no Windows: {command}")
        try:
            # Use shell=True with caution; here, it's necessary for schtasks.
            # Adding /F to force overwrite existing task.
            result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
            logging.info(f"Tarefa agendada com sucesso: {task_name}. Output: {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Erro ao agendar tarefa no Windows: {e}. Stderr: {e.stderr.strip()}")
        except Exception as e:
            logging.error(f"Erro inesperado ao agendar tarefa no Windows: {e}")
    else: # Linux/macOS
        cron_line: str = f"0 12 * * * python3 {script_path} --update"
        logging.info("Para agendar a atualização diária em sistemas Linux/macOS, adicione a seguinte linha ao seu crontab:")
        logging.info(f"  {cron_line}")
        logging.info("Você pode fazer isso executando 'crontab -e' no terminal e adicionando a linha.")

def connect_external_db(conn_str: str) -> Optional[sqlite3.Connection]:
    """
    Conecta-se a um banco de dados externo (exemplo para SQLite).
    Pode ser adaptado para outros tipos de banco de dados (PostgreSQL, MySQL, etc.)
    requerendo as bibliotecas apropriadas (e.g., psycopg2, mysql-connector-python).
    """
    logging.info(f"Tentando conectar ao banco de dados externo com: {conn_str}")
    try:
        # For SQLite, conn_str is typically the path to the database file
        conn = sqlite3.connect(conn_str, timeout=20.0)
        logging.info("Conexão com o banco de dados externo estabelecida.")
        return conn
    except sqlite3.Error as e:
        logging.error(f"Erro ao conectar ao banco de dados SQLite externo: {e}")
        return None
    except Exception as e:
        logging.error(f"Erro inesperado ao conectar ao banco de dados externo: {e}")
        return None

# --- Novas Funcionalidades ---
def filter_draws_by_period(draws: List[Draw], start_date: Optional[datetime.date] = None, end_date: Optional[datetime.date] = None) -> List[Draw]:
    """
    Filtra os sorteios por um período de datas.
    """
    if not start_date and not end_date:
        return draws
    
    filtered_draws: List[Draw] = []
    for d, nums in draws:
        if start_date and d < start_date:
            continue
        if end_date and d > end_date:
            continue
        filtered_draws.append((d, nums))
    return filtered_draws

def get_most_frequent_pairs(draws: List[Draw], k: int = NUM_DEZENAS) -> List[Tuple[Tuple[int, int], int]]:
    """
    Calcula os k pares de números mais frequentes em todos os sorteios.
    Retorna uma lista de tuplas (par, frequência).
    """
    counter: Counter = Counter()
    for _, nums in draws:
        # Ensure numbers are sorted within the tuple for consistent counting
        for pair in combinations(sorted(nums), 2):
            counter[pair] += 1
    return counter.most_common(k)

def get_most_frequent_triplets(draws: List[Draw], k: int = NUM_DEZENAS) -> List[Tuple[Tuple[int, int, int], int]]:
    """
    Calcula os k trios de números mais frequentes em todos os sorteios.
    Retorna uma lista de tuplas (trio, frequência).
    """
    counter: Counter = Counter()
    for _, nums in draws:
        # Ensure numbers are sorted within the tuple for consistent counting
        for triplet in combinations(sorted(nums), 3):
            counter[triplet] += 1
    return counter.most_common(k)

def conditional_probability(draws: List[Draw], given: int, target: int) -> float:
    """
    Calcula a probabilidade condicional de 'target' ser sorteado, dado que 'given' foi sorteado.
    P(Target | Given) = P(Target e Given) / P(Given)
    """
    if not (1 <= given <= MAX_NUM_MEGA_SENA) or not (1 <= target <= MAX_NUM_MEGA_SENA):
        logging.error(f"Números 'given' ({given}) e/ou 'target' ({target}) fora do intervalo válido (1-{MAX_NUM_MEGA_SENA}).")
        return 0.0
    if given == target:
        logging.warning("Probabilidade condicional de um número dado ele mesmo é 1.0 (se ele já saiu).")
        return 1.0

    count_given: int = 0
    count_both: int = 0
    for _, nums in draws:
        if given in nums:
            count_given += 1
            if target in nums:
                count_both += 1
    
    if count_given == 0:
        logging.warning(f"O número {given} nunca foi sorteado, não é possível calcular a probabilidade condicional.")
        return 0.0
    
    return count_both / count_given

def run_web_interface(draws: List[Draw]) -> None:
    """
    Inicia uma interface web Flask para exibir estatísticas.
    """
    if not Flask:
        logging.error("Flask não está instalado. Não é possível iniciar a interface web.")
        return

    app = Flask(__name__)

    @app.route("/frequencia")
    def frequencia():
        if request is None:
            return {"error": "Flask/Request support não disponível."}, 500
        top = int(request.args.get("top", NUM_DEZENAS))
        result = get_most_frequent(draws, top)
        if jsonify is None:
            return {"error": "Flask/JSON support não disponível."}, 500
        return jsonify(result)

    @app.route("/pares")
    def pares():
        if request is None:
            return {"error": "Flask/Request support não disponível."}, 500
        top = int(request.args.get("top", NUM_DEZENAS))
        result = get_most_frequent_pairs(draws, top)
        # Convert tuple keys to string for JSON serialization
        if jsonify is None:
            return {"error": "Flask 'jsonify' não está disponível. Instale Flask para usar esta funcionalidade."}
        return jsonify({str(pair): freq for pair, freq in result})

    @app.route("/trios")
    def trios():
        if request is None:
            return {"error": "Flask/Request support não disponível."}, 500
        top = int(request.args.get("top", NUM_DEZENAS))
        result = get_most_frequent_triplets(draws, top)
        # Convert tuple keys to string for JSON serialization
        if jsonify is None:
            return {"error": "Flask/JSON support não disponível."}, 500
        return jsonify({str(triplet): freq for triplet, freq in result})

    try:
        logging.info("Iniciando interface web Flask em http://127.0.0.1:5000")
        app.run(port=5000)
    except Exception as e:
        logging.error(f"Erro ao iniciar a interface web Flask: {e}")

# --- Análises Avançadas ---

def calculate_prediction_score(number: int, draws: List[Draw]) -> float:
    """Calcula score preditivo baseado em múltiplos fatores"""
    recent_weight = 0.4
    frequency_weight = 0.3
    gap_weight = 0.2
    correlation_weight = 0.1
    
    # Frequência recente
    recent_draws = draws[-50:] if len(draws) >= 50 else draws  # Últimos 50 sorteios
    recent_freq = sum(1 for _, nums in recent_draws if number in nums)
    recent_score = recent_freq / len(recent_draws) if recent_draws else 0
    
    # Frequência histórica
    total_freq = sum(1 for _, nums in draws if number in nums)
    freq_score = total_freq / len(draws) if draws else 0
    
    # Análise de gap (tempo desde última aparição)
    last_appearance = -1
    for i, (_, nums) in enumerate(reversed(draws)):
        if number in nums:
            last_appearance = i
            break
    
    gap_score = min(last_appearance / 20, 1.0) if last_appearance != -1 else 1.0
    
    # Score combinado
    final_score = (
        recent_score * recent_weight +
        freq_score * frequency_weight +
        gap_score * gap_weight
    )
    
    return final_score

def generate_smart_prediction(draws: List[Draw]) -> List[Tuple[int, float]]:
    """Gera predição inteligente com scores"""
    scores = []
    for num in range(1, MAX_NUM_MEGA_SENA + 1):
        score = calculate_prediction_score(num, draws)
        scores.append((num, score))
    
    return sorted(scores, key=lambda x: x[1], reverse=True)

def analyze_number_gaps(draws: List[Draw]) -> Dict[int, List[int]]:
    """Analisa intervalos entre aparições de cada número"""
    gaps = {i: [] for i in range(1, MAX_NUM_MEGA_SENA + 1)}
    last_appearance = {i: -1 for i in range(1, MAX_NUM_MEGA_SENA + 1)}
    
    for idx, (_, nums) in enumerate(draws):
        for num in nums:
            if last_appearance[num] != -1:
                gaps[num].append(idx - last_appearance[num])
            last_appearance[num] = idx
    
    return gaps

def analyze_cycles(draws: List[Draw]) -> Dict[str, Any]:
    """Identifica padrões cíclicos nos sorteios"""
    weekday_patterns = Counter()
    month_patterns = Counter()
    
    for date, nums in draws:
        weekday_patterns[date.weekday()] += 1
        month_patterns[date.month] += 1
    
    return {
        'weekday_distribution': dict(weekday_patterns),
        'month_distribution': dict(month_patterns)
    }

def analyze_sequences(draws: List[Draw]) -> Dict[str, Any]:
    """Analisa sequências numéricas nos sorteios"""
    consecutive_counts = Counter()
    arithmetic_sequences = Counter()
    
    for _, nums in draws:
        sorted_nums = sorted(nums)
        
        # Contar números consecutivos
        consecutive = 0
        for i in range(len(sorted_nums) - 1):
            if sorted_nums[i+1] == sorted_nums[i] + 1:
                consecutive += 1
        consecutive_counts[consecutive] += 1
        
        # Detectar progressões aritméticas
        for i in range(len(sorted_nums) - 2):
            diff1 = sorted_nums[i+1] - sorted_nums[i]
            diff2 = sorted_nums[i+2] - sorted_nums[i+1]
            if diff1 == diff2 and diff1 > 0:
                arithmetic_sequences[diff1] += 1
    
    return {
        'consecutive_distribution': dict(consecutive_counts),
        'arithmetic_progressions': dict(arithmetic_sequences)
    }

# --- User Sets & Backtesting Functions ---

def init_user_sets_db(path: str = USER_SETS_DB_PATH) -> None:
    """
    Inicializa a base de dados SQLite para os conjuntos de números do usuário.
    """
    try:
        with sqlite3.connect(path, timeout=20.0) as conn:
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    date_generated TEXT NOT NULL,
                    dez1 INTEGER, dez2 INTEGER, dez3 INTEGER,
                    dez4 INTEGER, dez5 INTEGER, dez6 INTEGER,
                    comparison_result TEXT,
                    comparison_concurso INTEGER,
                    UNIQUE(name)
                )
            ''')
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Erro ao inicializar o banco de dados de conjuntos do usuário: {e}")

def save_user_set(name: str, numbers: List[int], path: str = USER_SETS_DB_PATH) -> bool:
    """
    Salva um conjunto de 6 números gerados pelo usuário na base de dados.
    """
    init_user_sets_db(path)
    try:
        with sqlite3.connect(path, timeout=20.0) as conn:
            cursor: sqlite3.Cursor = conn.cursor()
            
            if len(numbers) != NUM_DEZENAS:
                logging.error(f"O conjunto de números deve conter {NUM_DEZENAS} dezenas.")
                return False

            sorted_numbers = sorted(numbers)
            date_generated = datetime.date.today().strftime('%Y-%m-%d')

            cursor.execute("SELECT id FROM user_sets WHERE name = ?", (name,))
            existing_id = cursor.fetchone()

            if existing_id:
                cursor.execute(f'''
                    UPDATE user_sets
                    SET date_generated = ?, dez1 = ?, dez2 = ?, dez3 = ?, dez4 = ?, dez5 = ?, dez6 = ?,
                        comparison_result = NULL, comparison_concurso = NULL
                    WHERE id = ?
                ''', (date_generated, *sorted_numbers, existing_id[0]))
                logging.info(f"Conjunto de números '{name}' atualizado.")
            else:
                cursor.execute(f'''
                    INSERT INTO user_sets (name, date_generated, dez1, dez2, dez3, dez4, dez5, dez6, comparison_result, comparison_concurso)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                ''', (name, date_generated, *sorted_numbers))
                logging.info(f"Novo conjunto de números '{name}' salvo.")
            
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        logging.error(f"Erro: Um conjunto com o nome '{name}' já existe.")
        return False
    except sqlite3.Error as e:
        logging.error(f"Erro ao salvar/atualizar conjunto de números do usuário: {e}")
        return False

def load_user_sets(path: str = USER_SETS_DB_PATH) -> List[Dict[str, Any]]:
    """
    Carrega todos os conjuntos de números salvos pelo usuário.
    """
    init_user_sets_db(path)
    user_sets: List[Dict[str, Any]] = []
    try:
        with sqlite3.connect(path, timeout=20.0) as conn:
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute('SELECT id, name, date_generated, dez1, dez2, dez3, dez4, dez5, dez6, comparison_result, comparison_concurso FROM user_sets')
            rows = cursor.fetchall()
            for row in rows:
                user_sets.append({
                    'id': row[0],
                    'name': row[1],
                    'date_generated': row[2],
                    'numbers': sorted([row[3], row[4], row[5], row[6], row[7], row[8]]),
                    'comparison_result': row[9],
                    'comparison_concurso': row[10]
                })
    except sqlite3.Error as e:
        logging.error(f"Erro ao carregar conjuntos de números do usuário: {e}")
    return user_sets

def delete_user_set(set_id: int, path: str = USER_SETS_DB_PATH) -> bool:
    """
    Deleta um conjunto de números do usuário pelo ID.
    """
    try:
        with sqlite3.connect(path, timeout=20.0) as conn:
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute("DELETE FROM user_sets WHERE id = ?", (set_id,))
            conn.commit()
            logging.info(f"Conjunto de números com ID {set_id} deletado.")
            return True
    except sqlite3.Error as e:
        logging.error(f"Erro ao deletar conjunto de números do usuário (ID: {set_id}): {e}")
        return False

def compare_user_sets_with_latest_draw(user_sets_path: str = USER_SETS_DB_PATH, mega_sena_db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Compara todos os conjuntos de números do usuário com o último sorteio da Mega-Sena.
    """
    latest_draw_data: Optional[Dict[str, Any]] = None
    try:
        latest_draw_api = fetch_lottery_data("megasena", None)
        latest_draw_data = {
            'concurso': int(latest_draw_api['concurso']),
            'dezenas': sorted(list(map(int, latest_draw_api['dezenas'])))
        }
    except Exception as e:
        logging.warning(f"Não foi possível buscar o último sorteio da API para comparação: {e}. Tentando usar o último do DB.")
        try:
            with sqlite3.connect(mega_sena_db_path, timeout=20.0) as conn_db:
                cursor_db = conn_db.cursor()
                cursor_db.execute('SELECT concurso, dez1, dez2, dez3, dez4, dez5, dez6 FROM megasena ORDER BY concurso DESC LIMIT 1')
                last_db_row = cursor_db.fetchone()
                if last_db_row:
                    latest_draw_data = {
                        'concurso': last_db_row[0],
                        'dezenas': sorted([last_db_row[i] for i in range(1, 7)])
                    }
        except Exception as e:
            logging.error(f"Erro ao obter o último sorteio do banco de dados local para comparação: {e}")
            return []

    if latest_draw_data is None:
        logging.error("Não foi possível obter o último sorteio da Mega-Sena.")
        return []

    latest_concurso_num = latest_draw_data['concurso']
    latest_dezenas = set(latest_draw_data['dezenas'])

    user_sets = load_user_sets(user_sets_path)
    comparison_results = []
    
    try:
        with sqlite3.connect(user_sets_path, timeout=20.0) as conn_user:
            cursor_user = conn_user.cursor()

            for user_set in user_sets:
                user_set_numbers = set(user_set['numbers'])
                matches = len(user_set_numbers.intersection(latest_dezenas))
                
                result_text = "Perdeu"
                if matches == 6: result_text = "Sena (6 acertos)!"
                elif matches == 5: result_text = "Quina (5 acertos)!"
                elif matches == 4: result_text = "Quadra (4 acertos)!"
                elif matches >= 3: result_text = f"Terno ({matches} acertos)" # Changed to >=3 to show matches
                else: result_text = f"Nenhum prêmio ({matches} acertos)"

                cursor_user.execute(f'''
                    UPDATE user_sets
                    SET comparison_result = ?, comparison_concurso = ?
                    WHERE id = ?
                ''', (result_text, latest_concurso_num, user_set['id']))
                
                user_set['comparison_result'] = result_text
                user_set['comparison_concurso'] = latest_concurso_num
                user_set['matches'] = matches
                user_set['latest_draw_dezenas'] = latest_draw_data['dezenas']
                
                comparison_results.append(user_set)
            
            conn_user.commit()

    except sqlite3.Error as e:
        logging.error(f"Erro ao atualizar resultados de comparação na base de dados de conjuntos do usuário: {e}")
    
    return comparison_results

def init_backtest_db(path: str = BACKTEST_DB_PATH) -> None:
    """
    Inicializa a base de dados para armazenar os resultados do backtest,
    criando a tabela 'backtest_results' se não existir.
    """
    try:
        with sqlite3.connect(path, timeout=20.0) as conn:
            cursor: sqlite3.Cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backtest_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    method TEXT NOT NULL,
                    date_tested TEXT NOT NULL,
                    generated_numbers TEXT NOT NULL,
                    draw_date TEXT NOT NULL,
                    matches INTEGER NOT NULL
                )
            ''')
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Erro ao inicializar o banco de dados de backtest: {e}")

def run_backtest(method: str) -> bool:
    """
    Executa o backtest para um método de geração de números e salva os resultados.
    """
    init_backtest_db()
    draws = load_all_draws()
    if not draws:
        logging.error('Base de dados vazia para backtest. Execute --update primeiro.')
        return False

    generated_numbers: Optional[List[int]] = []
    if method == "alltime":
        generated_numbers = get_most_frequent(draws)
    elif method == "lastyear":
        generated_numbers = get_most_frequent_period(draws)
    elif method == "weighted":
        generated_numbers = get_weighted(draws)
    else:
        logging.error(f"Método de backtest '{method}' não suportado.")
        return False

    if not generated_numbers:
        logging.warning(f"Não foi possível gerar números com o método '{method}' para backtest.")
        return False

    generated_set = set(generated_numbers)
    generated_numbers_str = ','.join(map(str, generated_numbers))
    date_tested = datetime.date.today().strftime('%Y-%m-%d')

    try:
        with sqlite3.connect(BACKTEST_DB_PATH, timeout=20.0) as conn:
            cursor: sqlite3.Cursor = conn.cursor()

            cursor.execute("DELETE FROM backtest_results WHERE method = ?", (method,))
            
            for draw_date, draw_numbers in draws:
                draw_set = set(draw_numbers)
                matches = len(generated_set.intersection(draw_set))
                cursor.execute('''
                    INSERT INTO backtest_results (method, date_tested, generated_numbers, draw_date, matches)
                    VALUES (?, ?, ?, ?, ?)
                ''', (method, date_tested, generated_numbers_str, str(draw_date), matches))

            conn.commit()
            logging.info(f"Backtest para o método '{method}' concluído com sucesso. Resultados salvos.")
            return True
    except sqlite3.Error as e:
        logging.error(f"Erro ao salvar os resultados do backtest: {e}")
        return False

def run_backtest_multiple(method: str, times: int = 1) -> Dict[str, Any]:
    """
    Executa o backtest múltiplas vezes para um método e retorna resumo consolidado.
    
    Args:
        method: Método de geração ('alltime', 'lastyear', 'weighted')
        times: Número de vezes a executar o backtest (padrão: 1)
    
    Returns:
        Dicionário com resumo consolidado dos backtests
    """
    if times < 1:
        logging.error("Número de backtests deve ser >= 1")
        return {'success': False, 'message': 'Número inválido', 'times_requested': 0, 'times_successful': 0, 'times_failed': 0}
    
    if times == 1:
        # Se for apenas 1, usa a função original mas retorna no mesmo formato
        success = run_backtest(method)
        return {
            'success': success,
            'times_executed': 1,
            'times_requested': 1,
            'times_successful': 1 if success else 0,
            'times_failed': 0 if success else 1,
            'method': method,
            'message': f"Backtest executado 1 vez com {'sucesso' if success else 'falha'}",
            'consolidated_numbers': [],
            'consolidated_frequency': {}
        }
    
    init_backtest_db()
    draws = load_all_draws()
    if not draws:
        logging.error('Base de dados vazia para backtest. Execute --update primeiro.')
        return {'success': False, 'times_executed': 0, 'message': 'Base de dados vazia'}
    
    logging.info(f"Iniciando {times} execuções de backtest para o método '{method}'...")
    
    total_results: Dict[str, int] = {}  # Armazenar resultados consolidados
    successful_runs = 0
    failed_runs = 0
    
    try:
        with sqlite3.connect(BACKTEST_DB_PATH, timeout=20.0) as conn:
            cursor: sqlite3.Cursor = conn.cursor()
            
            # Limpar dados anteriores
            cursor.execute("DELETE FROM backtest_results WHERE method = ?", (method,))
            conn.commit()
        
        for i in range(times):
            try:
                generated_numbers: Optional[List[int]] = []
                
                # Re-gerar números a cada iteração (para que sejam diferentes)
                if method == "alltime":
                    generated_numbers = get_most_frequent(draws)
                elif method == "lastyear":
                    generated_numbers = get_most_frequent_period(draws)
                elif method == "weighted":
                    generated_numbers = get_weighted(draws)
                else:
                    logging.error(f"Método de backtest '{method}' não suportado.")
                    failed_runs += 1
                    continue
                
                if not generated_numbers:
                    logging.warning(f"Execução {i+1}: Não foi possível gerar números.")
                    failed_runs += 1
                    continue
                
                generated_set = set(generated_numbers)
                generated_numbers_str = ','.join(map(str, generated_numbers))
                date_tested = datetime.date.today().strftime('%Y-%m-%d')
                
                with sqlite3.connect(BACKTEST_DB_PATH, timeout=20.0) as conn:
                    cursor: sqlite3.Cursor = conn.cursor()
                    
                    # Inserir resultados desta execução
                    for draw_date, draw_numbers in draws:
                        draw_set = set(draw_numbers)
                        matches = len(generated_set.intersection(draw_set))
                        cursor.execute('''
                            INSERT INTO backtest_results (method, date_tested, generated_numbers, draw_date, matches)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (method, date_tested, generated_numbers_str, str(draw_date), matches))
                    
                    conn.commit()
                
                logging.info(f"Execução {i+1}/{times} concluída com sucesso para método '{method}'")
                successful_runs += 1
                
                # Armazenar informação de quais números foram gerados
                key = f"exec_{i+1}_numbers"
                total_results[key] = generated_numbers
                
            except Exception as e:
                logging.error(f"Erro na execução {i+1} do backtest: {e}")
                failed_runs += 1
                continue
        
        # Consolidar números mais frequentes
        if successful_runs > 0:
            number_frequency: Dict[int, int] = {}
            for i in range(1, successful_runs + 1):
                key = f"exec_{i}_numbers"
                if key in total_results:
                    for num in total_results[key]:
                        number_frequency[num] = number_frequency.get(num, 0) + 1
            
            # Ordenar por frequência e pegar top 6
            consolidated = sorted(number_frequency.items(), key=lambda x: (-x[1], x[0]))[:6]
            total_results['consolidated_numbers'] = [num for num, _ in consolidated]
            total_results['consolidated_frequency'] = dict(consolidated)
        
        total_results['method'] = method
        total_results['times_requested'] = times
        total_results['times_successful'] = successful_runs
        total_results['times_failed'] = failed_runs
        total_results['success'] = successful_runs > 0
        total_results['message'] = f"Execução de backtests concluída: {successful_runs} sucesso(s), {failed_runs} falha(s) de {times}"
        
        logging.info(f"Backtests múltiplos concluídos: {successful_runs} sucesso(s), {failed_runs} falha(s)")
        
        return total_results
        
    except Exception as e:
        logging.error(f"Erro ao executar backtests múltiplos: {e}")
        return {
            'success': False,
            'times_executed': successful_runs,
            'message': f'Erro na execução: {str(e)}'
        }

def get_backtest_summary(method: str) -> Dict[str, Any]:
    """
    Carrega os resultados do backtest para um método e retorna um resumo.
    """
    summary = {
        'method': method,
        'numbers': [],
        'total_draws': 0,
        'matches': Counter()
    }
    try:
        with sqlite3.connect(BACKTEST_DB_PATH, timeout=20.0) as conn:
            cursor: sqlite3.Cursor = conn.cursor()
            
            cursor.execute("SELECT generated_numbers, COUNT(id) FROM backtest_results WHERE method = ? GROUP BY generated_numbers LIMIT 1", (method,))
            result = cursor.fetchone()
            if result:
                summary['numbers'] = [int(n) for n in result[0].split(',')]
                summary['total_draws'] = result[1]
            
            cursor.execute("SELECT matches, COUNT(*) FROM backtest_results WHERE method = ? GROUP BY matches", (method,))
            for matches, count in cursor.fetchall():
                summary['matches'][matches] = count
                
    except sqlite3.Error as e:
        logging.error(f"Erro ao carregar o resumo do backtest para o método '{method}': {e}")
    return summary

# --- Interface de Linha de Comando ---
def main() -> None:
    parser = argparse.ArgumentParser(description='Mega-Sena Analyzer')
    parser.add_argument('--update', action='store_true', help='Atualiza a base de dados local')
    parser.add_argument('--alltime', action='store_true', help='Top 6 de todos os tempos')
    parser.add_argument('--lastyear', action='store_true', help='Top 6 do último ano')
    parser.add_argument('--stat', action='store_true', help='Conjunto estatístico ponderado')
    parser.add_argument('--backtest-insights', nargs='?', const='weighted', choices=['alltime', 'lastyear', 'weighted'], help='Gera números usando histórico de backtest (opção: alltime, lastyear, weighted)')
    parser.add_argument('--db-path', type=str, help='Caminho personalizado para o banco de dados')
    parser.add_argument('--plot', action='store_true', help='Visualizar frequência dos números')
    parser.add_argument('--montecarlo', action='store_true', help='Simulação de Monte Carlo')
    parser.add_argument('--correlation', action='store_true', help='Calcular correlação entre números')
    parser.add_argument('--timeseries', action='store_true', help='Análise de séries temporais')
    parser.add_argument('--distribution', action='store_true', help='Análise de distribuição de probabilidade')
    parser.add_argument('--export', type=str, help='Exportar dados brutos dos sorteios (ex: --export dados.csv)')
    parser.add_argument('--period', nargs=2, metavar=('INICIO', 'FIM'), help='Filtrar por período (formato: AAAA-MM-DD)')
    parser.add_argument('--pairs', action='store_true', help='Exibe pares mais frequentes')
    parser.add_argument('--triplets', action='store_true', help='Exibe trios mais frequentes')
    parser.add_argument('--conditional', nargs=2, type=int, metavar=('GIVEN', 'TARGET'), help='Probabilidade de TARGET dado GIVEN')
    parser.add_argument('--export-analysis', nargs=2, metavar=('TIPO', 'ARQUIVO'), help='Exporta análise específica (frequencia, pares, trios, correlacao)')
    parser.add_argument('--schedule', action='store_true', help='Agendar atualização diária (crossplatform)')
    parser.add_argument('--external-db', type=str, help='String de conexão para banco de dados externo')
    parser.add_argument('--web', action='store_true', help='Inicia interface web Flask')
    parser.add_argument('--prediction', action='store_true', help='Geração inteligente de números com scoring')
    parser.add_argument('--backtest', nargs='?', const='weighted', choices=['alltime', 'lastyear', 'weighted'], help='Executa backtest (opção: alltime, lastyear, weighted)')
    parser.add_argument('--backtest-times', type=int, default=1, help='Número de vezes a executar o backtest (padrão: 1)')
    parser.add_argument('--gaps', action='store_true', help='Análise de intervalos entre aparições')
    parser.add_argument('--cycles', action='store_true', help='Análise de padrões cíclicos')
    parser.add_argument('--sequences', action='store_true', help='Análise de sequências numéricas')
    args = parser.parse_args()

    global DB_PATH
    if args.db_path:
        DB_PATH = args.db_path
    
    if args.external_db:
        external_conn = connect_external_db(args.external_db)
        if external_conn:
            external_conn.close()
            logging.info("Conexão com DB externo testada. As operações de DB continuarão a usar o DB local por padrão, a menos que o código seja adaptado.")
        else:
            logging.error("Falha ao conectar ao banco de dados externo. Operaçōes de banco de dados usarão o DB local.")


    if args.update:
        update_db()
        return

    draws: List[Draw] = []
    if any([args.alltime, args.lastyear, args.stat, args.backtest_insights, args.plot, args.montecarlo,
            args.correlation, args.timeseries, args.distribution, args.pairs,
            args.triplets, args.conditional, args.export_analysis, args.web, args.export,
            args.prediction, args.gaps, args.cycles, args.sequences]):
        draws = load_all_draws()
        if not draws:
            logging.error('Base vazia: execute com --update primeiro para baixar os dados.')
            return

    if args.period:
        try:
            start = datetime.datetime.strptime(args.period[0], "%Y-%m-%d").date()
            end = datetime.datetime.strptime(args.period[1], "%Y-%m-%d").date()
            if start > end:
                logging.error("Data de início não pode ser posterior à data de fim.")
                return
            draws = filter_draws_by_period(draws, start, end)
            if not draws:
                logging.warning(f"Nenhum sorteio encontrado no período de {args.period[0]} a {args.period[1]}.")
                return
        except ValueError as e:
            logging.error(f"Formato de data inválido. Use AAAA-MM-DD. Erro: {e}")
            return


    if args.alltime:
        result = get_most_frequent(draws)
        print('Top 6 de todos os tempos:', result)
    elif args.lastyear:
        result = get_most_frequent_period(draws)
        print('Top 6 do último ano:', result)
    elif args.stat:
        result = get_weighted(draws)
        print('Conjunto estatístico ponderado:', result)
    elif args.backtest_insights:
        result = get_from_backtest_insights(method=args.backtest_insights)
        print(f'Números gerados por insights de backtest ({args.backtest_insights}):', result)
    elif args.backtest:
        result = run_backtest_multiple(method=args.backtest, times=args.backtest_times)
        if result['success']:
            print(f'\n✓ Backtests executados com sucesso!')
            print(f'  Execuções solicitadas: {result["times_requested"]}')
            print(f'  Execuções bem-sucedidas: {result["times_successful"]}')
            if result['times_failed'] > 0:
                print(f'  Falhas: {result["times_failed"]}')
            
            consolidated = result.get('consolidated_numbers', [])
            freq = result.get('consolidated_frequency', {})
            
            if consolidated:
                print(f'\n📊 Números consolidados (mais frequentes): {consolidated}')
                if result['times_requested'] > 1:
                    print('  Frequência:')
                    for num in consolidated:
                        if num in freq:
                            count = freq[num][1] if isinstance(freq[num], tuple) else freq[num]
                            print(f'    {num}: apareceu {count}x em {result["times_successful"]} execuções')
            
            # Mostrar resultados individuais se houver
            if result['times_requested'] > 1:
                print('\n📋 Resultados individuais:')
                for i in range(1, result['times_successful'] + 1):
                    exec_key = f'exec_{i}_numbers'
                    if exec_key in result:
                        print(f'  Execução {i}: {result[exec_key]}')
        else:
            print(f'\n✗ Erro ao executar backtests: {result["message"]}')
    elif args.plot:
        plot_frequency(draws)
    elif args.montecarlo:
        simulated, real = monte_carlo_simulation(draws)
        print('Simulação de Monte Carlo - Números mais frequentes:')
        print('Simulados (Número, Frequência):', simulated)
        print('Reais (Número, Frequência):', real)
    elif args.correlation:
        correlation_matrix = calculate_correlation(draws)
        if correlation_matrix is not None:
            print('Matriz de Correlação:\n', correlation_matrix)
    elif args.timeseries:
        analyze_time_series(draws)
    elif args.distribution:
        chi2_p = analyze_probability_distribution(draws)
        if chi2_p:
            chi2, p = chi2_p
            print(f'Teste Qui-quadrado: Chi2 = {chi2:.4f}, p-valor = {p:.4f}')
            if p < 0.05:
                print("A distribuição observada é significativamente diferente de uma distribuição uniforme (com base no p-valor < 0.05).")
            else:
                print("A distribuição observada não é significativamente diferente de uma distribuição uniforme (com base no p-valor >= 0.05).")
    elif args.pairs:
        result = get_most_frequent_pairs(draws)
        print('Pares mais frequentes (Par, Frequência):', result)
    elif args.triplets:
        result = get_most_frequent_triplets(draws)
        print('Trios mais frequentes (Trio, Frequência):', result)
    elif args.conditional:
        given, target = args.conditional
        prob = conditional_probability(draws, given, target)
        print(f'Probabilidade de {target} ser sorteado, dado que {given} foi sorteado: P({target}|{given}) = {prob:.4f}')
    elif args.export_analysis:
        analysis_type, filename = args.export_analysis
        if analysis_type == "frequencia":
            counter_data = Counter()
            for _, nums in draws:
                counter_data.update(nums)
            export_results(counter_data.most_common(), file_format=filename.split('.')[-1], filename=filename.rsplit('.', 1)[0], header=["Número", "Frequência"])
        elif analysis_type == "pares":
            data = get_most_frequent_pairs(draws, k=20)
            export_results(data, file_format=filename.split('.')[-1], filename=filename.rsplit('.', 1)[0], header=["Par", "Frequência"])
        elif analysis_type == "trios":
            data = get_most_frequent_triplets(draws, k=20)
            export_results(data, file_format=filename.split('.')[-1], filename=filename.rsplit('.', 1)[0], header=["Trio", "Frequência"])
        elif analysis_type == "correlacao":
            corr_matrix = calculate_correlation(draws)
            if corr_matrix is not None:
                try:
                    sanitized_fn = sanitize_filename(filename.rsplit('.', 1)[0])
                    corr_matrix.to_csv(f"{sanitized_fn}.csv")
                    logging.info(f"Matriz de correlação exportada para {sanitized_fn}.csv")
                except ValueError as e:
                    logging.error(f"Erro ao exportar correlação: {e}")
            else:
                logging.warning("Não foi possível gerar a matriz de correlação para exportação.")
        else:
            logging.error(f"Tipo de análise para exportação '{analysis_type}' não suportado.")
    elif args.schedule:
        schedule_task_crossplatform()
    elif args.web:
        run_web_interface(draws)
    elif args.prediction:
        prediction = generate_smart_prediction(draws)
        print('Predição Inteligente (Top 10 com scores):')
        for i, (num, score) in enumerate(prediction[:10], 1):
            print(f"{i:2d}. Número {num:2d}: Score {score:.4f}")
        
        top_6 = [num for num, _ in prediction[:6]]
        print(f'\nTop 6 Sugeridos: {top_6}')
    elif args.gaps:
        gaps = analyze_number_gaps(draws)
        print('Análise de Intervalos (números com maior gap médio):')
        avg_gaps = {num: sum(gap_list)/len(gap_list) if gap_list else 0 
                   for num, gap_list in gaps.items()}
        sorted_gaps = sorted(avg_gaps.items(), key=lambda x: x[1], reverse=True)
        for i, (num, avg_gap) in enumerate(sorted_gaps[:10], 1):
            print(f"{i:2d}. Número {num:2d}: Gap médio {avg_gap:.1f}")
    elif args.cycles:
        cycles = analyze_cycles(draws)
        print('Análise de Padrões Cíclicos:')
        print('\nDistribuição por dia da semana:')
        weekdays = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        for day, freq in cycles['weekday_distribution'].items():
            print(f"  {weekdays[day]}: {freq} sorteios")
        
        print('\nDistribuição por mês:')
        months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 
                 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        for month, freq in cycles['month_distribution'].items():
            print(f"  {months[month-1]}: {freq} sorteios")
    elif args.sequences:
        sequences = analyze_sequences(draws)
        print('Análise de Sequências:')
        print('\nDistribuição de números consecutivos:')
        for consec, freq in sorted(sequences['consecutive_distribution'].items()):
            print(f"  {consec} consecutivos: {freq} sorteios")
        
        print('\nProgressões aritméticas mais comuns:')
        for diff, freq in sorted(sequences['arithmetic_progressions'].items(), 
                                key=lambda x: x[1], reverse=True)[:5]:
            print(f"  Diferença {diff}: {freq} ocorrências")
    elif args.export:
        export_data = []
        for d, nums in draws:
            export_data.append([d.strftime('%Y-%m-%d')] + list(nums))
        
        export_results(
            export_data, 
            file_format=args.export.split('.')[-1], 
            filename=args.export.rsplit('.', 1)[0],
            header=['Data'] + [f'Dezena{i+1}' for i in range(NUM_DEZENAS)]
        )
    else:
        parser.print_help()

if __name__ == '__main__':
    main()


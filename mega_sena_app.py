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
from collections import Counter
from itertools import combinations
from typing import List, Tuple, Dict, Any, Optional

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
DB_PATH: str = os.getenv('MEGASENA_DB_PATH', 'megasena.db')
API_BASE: str = 'https://loteriascaixa-api.herokuapp.com/api/megasena'

# Constants
NUM_DEZENAS: int = 6
MAX_NUM_MEGA_SENA: int = 60

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Type alias for better readability
Draw = Tuple[datetime.date, Tuple[int, int, int, int, int, int]]


# --- Banco de Dados ---
def init_db(path: str = DB_PATH) -> None:
    """
    Inicializa a base de dados SQLite, criando a tabela megasena se não existir.
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(path)
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS megasena (
                concurso INTEGER PRIMARY KEY,
                data TEXT,
                dez1 INTEGER, dez2 INTEGER, dez3 INTEGER,
                dez4 INTEGER, dez5 INTEGER, dez6 INTEGER
            )
        ''')
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Erro ao inicializar o banco de dados: {e}")
    finally:
        if conn:
            conn.close()

def get_last_db_concurso(path: str = DB_PATH) -> int:
    """
    Retorna o número do último concurso registrado no banco de dados.
    Retorna 0 se o banco de dados estiver vazio ou houver um erro.
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(path)
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute('SELECT MAX(concurso) FROM megasena')
        row = cursor.fetchone()
        return row[0] or 0
    except sqlite3.Error as e:
        logging.error(f"Erro ao obter o último concurso do banco de dados: {e}")
        return 0
    finally:
        if conn:
            conn.close()

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

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(path)
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
    except sqlite3.Error as e:
        logging.error(f"Erro ao inserir dados no banco de dados: {e}")
    finally:
        if conn:
            conn.close()

# --- Cálculos Estatísticos ---
def load_all_draws(path: str = DB_PATH) -> List[Draw]:
    """
    Carrega todos os sorteios da Mega-Sena do banco de dados.
    Retorna uma lista de tuplas (data, dezenas).
    """
    conn: Optional[sqlite3.Connection] = None
    draws: List[Draw] = []
    try:
        conn = sqlite3.connect(path)
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
    except sqlite3.Error as e:
        logging.error(f"Erro ao carregar sorteios do banco de dados: {e}")
    finally:
        if conn:
            conn.close()
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

def monte_carlo_simulation(draws: List[Draw], simulations: int = 10000) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """
    Realiza uma simulação de Monte Carlo para comparar frequências simuladas com as reais.
    Retorna os 6 números mais frequentes simulados e reais.
    """
    if not np:
        logging.error("NumPy não está instalado. Não é possível realizar a simulação de Monte Carlo.")
        return [], []

    all_nums: List[int] = list(range(1, MAX_NUM_MEGA_SENA + 1))
    simulated_counts: Counter = Counter()

    for _ in range(simulations):
        # Simulate a draw of 6 unique numbers
        simulated_draw = np.random.choice(all_nums, size=NUM_DEZENAS, replace=False)
        simulated_counts.update(simulated_draw)

    real_counts: Counter = Counter()
    for _, nums in draws:
        real_counts.update(nums)
        
    most_simulated: List[Tuple[int, int]] = simulated_counts.most_common(NUM_DEZENAS)
    most_real: List[Tuple[int, int]] = real_counts.most_common(NUM_DEZENAS)
    return most_simulated, most_real

def calculate_correlation(draws: List[Draw]) -> Optional[Any]:
    """
    Calcula a matriz de correlação entre os números sorteados.
    """
    if not pd:
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
        conn = sqlite3.connect(conn_str)
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
        if request is None or not hasattr(request, "args"):
            return {"error": "Flask/Request support não disponível."}, 500
        if request is None or not hasattr(request, "args"):
            return {"error": "Flask/Request support não disponível."}, 500
        top = int(request.args.get("top", NUM_DEZENAS))
        result = get_most_frequent(draws, top)
        if jsonify is None:
            return {"error": "Flask/JSON support não disponível."}, 500
        return jsonify(result)

    @app.route("/pares")
    def pares():
        top = int(request.args.get("top", NUM_DEZENAS))
        result = get_most_frequent_pairs(draws, top)
        # Convert tuple keys to string for JSON serialization
        if jsonify is None:
            return {"error": "Flask/JSON support não disponível."}, 500
        return jsonify({str(pair): freq for pair, freq in result})

    @app.route("/trios")
    def trios():
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

# --- Banco de Dados do Usuário ---
USER_SETS_DB_PATH: str = os.getenv('MEGASENA_USER_SETS_DB_PATH', 'user_sets.db')

def init_user_sets_db(path: str = USER_SETS_DB_PATH) -> None:
    """
    Inicializa a base de dados SQLite para os conjuntos de números do usuário,
    criando a tabela 'user_sets' se não existir.
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
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
    finally:
        if conn:
            conn.close()

def save_user_set(name: str, numbers: List[int], path: str = USER_SETS_DB_PATH) -> bool:
    """
    Salva um conjunto de 6 números gerados pelo usuário na base de dados.
    Atualiza um conjunto existente se o nome for o mesmo, caso contrário, insere um novo.
    """
    init_user_sets_db(path)
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        if len(numbers) != NUM_DEZENAS:
            logging.error(f"O conjunto de números deve conter {NUM_DEZENAS} dezenas.")
            return False
        sorted_numbers = sorted(numbers)
        date_generated = datetime.date.today().strftime('%Y-%m-%d')
        cursor.execute("SELECT id FROM user_sets WHERE name = ?", (name,))
        existing_id = cursor.fetchone()
        if existing_id:
            cursor.execute('''
                UPDATE user_sets
                SET date_generated = ?, dez1 = ?, dez2 = ?, dez3 = ?, dez4 = ?, dez5 = ?, dez6 = ?,
                    comparison_result = NULL, comparison_concurso = NULL
                WHERE id = ?
            ''', (date_generated, *sorted_numbers, existing_id[0]))
            logging.info(f"Conjunto de números '{name}' atualizado.")
        else:
            cursor.execute('''
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
    finally:
        if conn:
            conn.close()

def load_user_sets(path: str = USER_SETS_DB_PATH) -> List[Dict[str, Any]]:
    """
    Carrega todos os conjuntos de números salvos pelo usuário.
    """
    init_user_sets_db(path)
    conn: Optional[sqlite3.Connection] = None
    user_sets: List[Dict[str, Any]] = []
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
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
    finally:
        if conn:
            conn.close()
    return user_sets

def delete_user_set(set_id: int, path: str = USER_SETS_DB_PATH) -> bool:
    """
    Deleta um conjunto de números do usuário pelo ID.
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_sets WHERE id = ?", (set_id,))
        conn.commit()
        logging.info(f"Conjunto de números com ID {set_id} deletado.")
        return True
    except sqlite3.Error as e:
        logging.error(f"Erro ao deletar conjunto de números do usuário (ID: {set_id}): {e}")
        return False
    finally:
        if conn:
            conn.close()

def compare_user_sets_with_latest_draw(user_sets_path: str = USER_SETS_DB_PATH, mega_sena_db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Compara todos os conjuntos de números do usuário com o último sorteio da Mega-Sena.
    Atualiza o banco de dados do usuário com os resultados da comparação.
    Retorna uma lista de dicionários com os resultados da comparação.
    """
    latest_draw_data: Optional[Dict[str, Any]] = None
    try:
        all_draws = load_all_draws(mega_sena_db_path)
        if not all_draws:
            logging.warning("Base de dados da Mega-Sena vazia. Não é possível comparar os conjuntos.")
            return []
        latest_concurso_db = get_last_db_concurso(mega_sena_db_path)
        latest_draw_tuple = None
        for d, nums in all_draws:
            try:
                latest_draw_api = fetch_lottery_data("megasena", None)
                latest_draw_number = int(latest_draw_api['concurso'])
                latest_draw_dezenas = sorted(list(map(int, latest_draw_api['dezenas'])))
                latest_draw_data = {
                    'concurso': latest_draw_number,
                    'dezenas': latest_draw_dezenas
                }
                break
            except Exception as e:
                logging.warning(f"Não foi possível buscar o último sorteio da API para comparação: {e}. Tentando usar o último do DB.")
                if all_draws:
                    conn_db = sqlite3.connect(mega_sena_db_path)
                    cursor_db = conn_db.cursor()
                    cursor_db.execute('SELECT concurso, data, dez1, dez2, dez3, dez4, dez5, dez6 FROM megasena ORDER BY concurso DESC LIMIT 1')
                    last_db_row = cursor_db.fetchone()
                    conn_db.close()
                    if last_db_row:
                        latest_draw_data = {
                            'concurso': last_db_row[0],
                            'dezenas': sorted([last_db_row[i] for i in range(2, 8)])
                        }
                    else:
                        return []
                else:
                    return []
    except Exception as e:
        logging.error(f"Erro ao obter o último sorteio da Mega-Sena para comparação: {e}")
        return []
    if latest_draw_data is None:
        return []
    latest_concurso_num = latest_draw_data['concurso']
    latest_dezenas = set(latest_draw_data['dezenas'])
    user_sets = load_user_sets(user_sets_path)
    comparison_results = []
    conn_user = None
    try:
        conn_user = sqlite3.connect(user_sets_path)
        cursor_user = conn_user.cursor()
        for user_set in user_sets:
            user_set_numbers = set(user_set['numbers'])
            matches = len(user_set_numbers.intersection(latest_dezenas))
            result_text = "Perdeu"
            if matches == 6:
                result_text = "Sena (6 acertos)!"
            elif matches == 5:
                result_text = "Quina (5 acertos)!"
            elif matches == 4:
                result_text = "Quadra (4 acertos)!"
            elif matches == 3:
                result_text = "Terno (3 acertos)"
            else:
                result_text = f"Nenhum prêmio ({matches} acertos)"
            cursor_user.execute('''
                UPDATE user_sets
                SET comparison_result = ?, comparison_concurso = ?
                WHERE id = ?
            ''', (result_text, latest_concurso_num, user_set['id']))
            user_set['comparison_result'] = result_text
            user_set['comparison_concurso'] = latest_concurso_num
            user_set['matches'] = matches
            user_set['latest_draw_dezenas'] = sorted(list(latest_dezenas))
            comparison_results.append(user_set)
        conn_user.commit()
    except sqlite3.Error as e:
        logging.error(f"Erro ao atualizar resultados de comparação na base de dados de conjuntos do usuário: {e}")
    finally:
        if conn_user:
            conn_user.close()
    return comparison_results

# --- Interface de Linha de Comando ---
USER_BETS_FILE = "apostas_usuario.csv"


def salvar_aposta_usuario(numeros: list, origem: str):
    """
    Salva o conjunto de 6 números escolhido pelo usuário em um arquivo separado.
    """
    import csv
    from datetime import datetime
    if len(numeros) != 6:
        raise ValueError("A aposta deve conter exatamente 6 números.")
    numeros_ordenados = sorted(numeros)
    existe = os.path.exists(USER_BETS_FILE)
    with open(USER_BETS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not existe:
            writer.writerow(["data_aposta", "origem", "n1", "n2", "n3", "n4", "n5", "n6"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), origem] + numeros_ordenados)
    print(f"Aposta salva em {USER_BETS_FILE}: {numeros_ordenados}")


def comparar_aposta_com_ultimo_resultado():
    """
    Compara a última aposta salva pelo usuário com o último resultado oficial da Mega-Sena.
    """
    import csv
    if not os.path.exists(USER_BETS_FILE):
        print("Nenhuma aposta de usuário encontrada.")
        return
    # Carrega última aposta
    with open(USER_BETS_FILE, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        if len(reader) < 2:
            print("Nenhuma aposta registrada.")
            return
        header, *rows = reader
        ultima_aposta = rows[-1]
        aposta_nums = set(map(int, ultima_aposta[2:]))
        origem = ultima_aposta[1]
        data_aposta = ultima_aposta[0]
    # Carrega último sorteio
    draws = load_all_draws()
    if not draws:
        print("Base de dados vazia. Atualize primeiro.")
        return
    data_ultimo, dezenas_ultimo = draws[-1]
    acertos = aposta_nums.intersection(set(dezenas_ultimo))
    print(f"Aposta feita em {data_aposta} (origem: {origem}): {sorted(aposta_nums)}")
    print(f"Resultado oficial do sorteio {data_ultimo}: {sorted(dezenas_ultimo)}")
    print(f"Números acertados: {sorted(acertos)} ({len(acertos)} acertos)")


def calcular_nivel_confianca(draws: List[Draw], conjunto: List[int]) -> float:
    """
    Calcula um nível de confiança empírico para um conjunto de 6 números.
    Aqui, soma as frequências relativas de cada número no histórico.
    """
    counter = Counter()
    for _, nums in draws:
        counter.update(nums)
    total = sum(counter.values())
    if total == 0:
        return 0.0
    prob = sum(counter[n] for n in conjunto) / total
    # Normaliza para um valor entre 0 e 1 (ou 0% a 100%)
    return prob

def salvar_jogo_usuario(conjunto: List[int], modo: str, nivel_confianca: float, arquivo: str = "meus_jogos.csv"):
    """
    Salva o conjunto de números gerado pelo usuário em um arquivo separado.
    """
    import csv
    from datetime import datetime
    existe = os.path.exists(arquivo)
    with open(arquivo, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not existe:
            writer.writerow(["data", "modo", "numeros", "nivel_confianca"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), modo, "-".join(map(str, conjunto)), f"{nivel_confianca:.4f}"])
    print(f"Jogo salvo em {arquivo}: {conjunto} (Nível de confiança: {nivel_confianca:.4f})")


def main():
    parser = argparse.ArgumentParser(description='Mega-Sena Analyzer')
    parser.add_argument('--update', action='store_true', help='Atualiza a base de dados local')
    parser.add_argument('--alltime', action='store_true', help='Top 6 de todos os tempos')
    parser.add_argument('--lastyear', action='store_true', help='Top 6 do último ano')
    parser.add_argument('--stat', action='store_true', help='Conjunto estatístico ponderado')
    parser.add_argument('--db-path', type=str, help='Caminho personalizado para o banco de dados')
    parser.add_argument('--plot', action='store_true', help='Visualizar frequência dos números')
    parser.add_argument('--montecarlo', action='store_true', help='Simulação de Monte Carlo')
    parser.add_argument('--correlation', action='store_true', help='Calcular correlação entre números')
    parser.add_argument('--timeseries', action='store_true', help='Análise de séries temporais')
    parser.add_argument('--distribution', action='store_true', help='Análise de distribuição de probabilidade')
    parser.add_argument('--export', type=str, help='Exportar dados brutos dos sorteios (ex: --export dados.csv)')
    # Novos argumentos
    parser.add_argument('--period', nargs=2, metavar=('INICIO', 'FIM'), help='Filtrar por período (formato: AAAA-MM-DD)')
    parser.add_argument('--pairs', action='store_true', help='Exibe pares mais frequentes')
    parser.add_argument('--triplets', action='store_true', help='Exibe trios mais frequentes')
    parser.add_argument('--conditional', nargs=2, type=int, metavar=('GIVEN', 'TARGET'), help='Probabilidade de TARGET dado GIVEN')
    parser.add_argument('--export-analysis', nargs=2, metavar=('TIPO', 'ARQUIVO'), help='Exporta análise específica (frequencia, pares, trios, correlacao)')
    parser.add_argument('--schedule', action='store_true', help='Agendar atualização diária (crossplatform)')
    parser.add_argument('--external-db', type=str, help='String de conexão para banco de dados externo')
    parser.add_argument('--web', action='store_true', help='Inicia interface web Flask')
    parser.add_argument('--salvar-aposta', choices=['frequencia', 'ponderado'], help='Gera e salva aposta baseada em frequência ou ponderação')
    parser.add_argument('--comparar-aposta', action='store_true', help='Compara a última aposta salva com o último sorteio oficial')
    parser.add_argument('--salvar-user-set', nargs=2, metavar=('MODO', 'NOME'), help='Salva um conjunto de 6 números gerado pelo modo (frequencia|ponderado) com o nome especificado')
    parser.add_argument('--comparar-user-sets', action='store_true', help='Compara todos os conjuntos do usuário com o último sorteio oficial')
    args = parser.parse_args()

    global DB_PATH
    if args.db_path:
        DB_PATH = args.db_path
    
    # Handle external database connection (if provided)
    if args.external_db:
        # The 'connect_external_db' function currently just connects to SQLite.
        # For other DBs, you'd need to adapt database functions (init_db, get_last_db_concurso, update_db, load_all_draws)
        # to use the new connection object or a custom ORM/DBAL.
        # For this example, we'll just log the connection attempt.
        external_conn = connect_external_db(args.external_db)
        if external_conn:
            # If you were to fully integrate, you'd pass external_conn to relevant functions
            # For now, just close it if it was successfully opened.
            external_conn.close()
            logging.info("Conexão com DB externo testada. As operações de DB continuarão a usar o DB local por padrão, a menos que o código seja adaptado.")
        else:
            logging.error("Falha ao conectar ao banco de dados externo. Operações de banco de dados usarão o DB local.")


    def handle_update():
        update_db()

    def handle_analysis(draws):
        if args.alltime:
            result = get_most_frequent(draws)
            print('Top 6 de todos os tempos:', result)
        elif args.lastyear:
            result = get_most_frequent_period(draws)
            print('Top 6 do último ano:', result)
        elif args.stat:
            result = get_weighted(draws)
            print('Conjunto estatístico ponderado:', result)
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

    def handle_export_analysis(draws):
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

    def handle_schedule():
        schedule_task_crossplatform()

    def handle_web(draws):
        run_web_interface(draws)

    def handle_export(draws):
        export_data = []
        for d, nums in draws:
            export_data.append([d.strftime('%Y-%m-%d')] + list(nums))
        export_results(
            export_data,
            file_format=args.export.split('.')[-1],
            filename=args.export.rsplit('.', 1)[0],
            header=['Data'] + [f'Dezena{i+1}' for i in range(NUM_DEZENAS)]
        )

    def handle_salvar_aposta():
        draws = load_all_draws()
        if not draws:
            print('Base vazia: execute com --update primeiro')
            return
        if args.salvar_aposta == 'frequencia':
            numeros = get_most_frequent(draws)
            salvar_aposta_usuario(numeros, 'frequencia')
        elif args.salvar_aposta == 'ponderado':
            numeros = get_weighted(draws)
            salvar_aposta_usuario(numeros, 'ponderado')

    def handle_comparar_aposta():
        comparar_aposta_com_ultimo_resultado()

    def handle_salvar_user_set():
        modo, nome = args.salvar_user_set
        if modo not in ['frequencia', 'ponderado']:
            print("Modo inválido. Use 'frequencia' ou 'ponderado'.")
            return
        draws = load_all_draws()
        if not draws:
            print('Base vazia: execute com --update primeiro')
            return
        if modo == 'frequencia':
            numeros = get_most_frequent(draws)
        else:
            numeros = get_weighted(draws)
        ok = save_user_set(nome, numeros)
        if ok:
            print(f"Conjunto '{nome}' salvo com sucesso: {numeros}")
        else:
            print(f"Falha ao salvar conjunto '{nome}'.")

    def handle_comparar_user_sets():
        results = compare_user_sets_with_latest_draw()
        for res in results:
            print(f"Conjunto '{res['name']}' ({res['numbers']}) - Resultado: {res['comparison_result']} (Concurso: {res['comparison_concurso']})")

    # --- Execução dos comandos ---
    if args.update:
        handle_update()
        return

    draws: List[Draw] = []
    if any([args.alltime, args.lastyear, args.stat, args.plot, args.montecarlo,
            args.correlation, args.timeseries, args.distribution, args.pairs,
            args.triplets, args.conditional, args.export_analysis, args.web, args.export]):
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

    if args.alltime or args.lastyear or args.stat or args.plot or args.montecarlo or args.correlation or args.timeseries or args.distribution or args.pairs or args.triplets or args.conditional:
        handle_analysis(draws)
        return
    if args.export_analysis:
        handle_export_analysis(draws)
        return
    if args.schedule:
        handle_schedule()
        return
    if args.web:
        handle_web(draws)
        return
    if args.export:
        handle_export(draws)
        return
    if args.salvar_aposta:
        handle_salvar_aposta()
        return
    if args.comparar_aposta:
        handle_comparar_aposta()
        return
    if args.salvar_user_set:
        handle_salvar_user_set()
        return
    if args.comparar_user_sets:
        handle_comparar_user_sets()
        return
    parser.print_help()

if __name__ == '__main__':
    main()
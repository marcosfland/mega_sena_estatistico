#!/usr/bin/env python3
"""
Mega-Sena Analyzer

Este script cria/atualiza a base de dados local (SQLite) com resultados da Mega-Sena via API pública,
calcula os 6 números mais frequentes de todos os tempos, dos últimos 365 dias e um conjunto estatístico
ponderado.

Dependências:
    pip install requests

Uso:
    python mega_sena_app.py --update   # Atualiza a base de dados local
    python mega_sena_app.py --alltime  # Exibe top 6 de todos os tempos
    python mega_sena_app.py --lastyear # Exibe top 6 do último ano
    python mega_sena_app.py --stat     # Exibe conjunto estatístico ponderado
"""

import argparse
import datetime
import os
import sqlite3
import sys
import requests
from collections import Counter
import random
import logging
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chisquare
import json
import csv
import subprocess

# Configurações
DB_PATH = os.getenv('MEGASENA_DB_PATH', 'megasena.db')
API_BASE = 'https://loteriascaixa-api.herokuapp.com/api/megasena'

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ---------------------
# Banco de Dados
# ---------------------

def init_db(path: str = DB_PATH):
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS megasena (
            concurso INTEGER PRIMARY KEY,
            data TEXT,
            dez1 INTEGER, dez2 INTEGER, dez3 INTEGER,
            dez4 INTEGER, dez5 INTEGER, dez6 INTEGER
        )
    ''')
    conn.commit()
    conn.close()

# ---------------------
# API Integration
# ---------------------

API_LOTERIAS = {
    "megasena": "https://loteriascaixa-api.herokuapp.com/api/megasena",
    "quina": "https://loteriascaixa-api.herokuapp.com/api/quina",
    "lotofacil": "https://loteriascaixa-api.herokuapp.com/api/lotofacil"
}

def fetch_lottery_data(lottery="megasena", concurso=None):
    url = f"{API_LOTERIAS[lottery]}/{concurso}" if concurso else f"{API_LOTERIAS[lottery]}/latest"
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logging.error(f"Erro ao buscar dados da API para {lottery}: {e}")
        raise

from typing import Optional

def fetch_concurso(concurso: Optional[int] = None) -> dict:
    """Busca JSON de um concurso específico ou último se concurso=None"""
    url = f"{API_BASE}/{concurso}" if concurso else API_BASE + '/latest'
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        if not validate_api_data(data):
            raise ValueError(f"Dados inválidos recebidos para o concurso {concurso}")
        return data
    except requests.RequestException as e:
        logging.error(f"Erro ao buscar dados da API: {e}")
        raise
    except ValueError as e:
        logging.error(e)
        raise

def validate_api_data(data: dict) -> bool:
    """Valida os dados retornados pela API"""
    required_keys = {'concurso', 'data', 'dezenas'}
    if not all(key in data for key in required_keys):
        return False
    if not isinstance(data['dezenas'], list) or len(data['dezenas']) != 6:
        return False
    return True

# ---------------------
# Atualização de Dados
# ---------------------

def get_last_db_concurso(path: str = DB_PATH) -> int:
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute('SELECT MAX(concurso) FROM megasena')
    row = cursor.fetchone()
    conn.close()
    return row[0] or 0

def update_db(path: str = DB_PATH):
    init_db(path)
    ultimo_db = get_last_db_concurso(path)
    try:
        data_last = fetch_concurso(None)
        ultimo_api = int(data_last['concurso'])
    except Exception as e:
        logging.error(f"Erro ao obter último concurso da API: {e}")
        return

    if ultimo_api <= ultimo_db:
        logging.info(f"Base já está atualizada até o concurso {ultimo_db}")
        return

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    for concurso in range(ultimo_db + 1, ultimo_api + 1):
        try:
            jogo = fetch_concurso(concurso)
        except Exception as e:
            logging.warning(f"Concurso {concurso} indisponível ou inválido: {e}")
            continue
        dezenas = list(map(int, jogo['dezenas']))
        cursor.execute('''
            INSERT OR IGNORE INTO megasena
            (concurso, data, dez1, dez2, dez3, dez4, dez5, dez6)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (concurso, jogo['data'], *dezenas))
        logging.info(f"Inserido concurso {concurso}")

    conn.commit()
    conn.close()
    logging.info(f"Atualização concluída até o concurso {ultimo_api}")

# ---------------------
# Cálculos Estatísticos
# ---------------------

def load_all_draws(path: str = DB_PATH):
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute('SELECT data, dez1, dez2, dez3, dez4, dez5, dez6 FROM megasena')
    rows = cursor.fetchall()
    conn.close()
    draws = []
    for data_str, *dez in rows:
        date = datetime.datetime.strptime(data_str, '%d/%m/%Y').date()
        draws.append((date, tuple(dez)))
    return draws

def get_most_frequent(draws, k: int = 6):
    counter = Counter()
    for _, nums in draws:
        counter.update(nums)
    return [num for num, _ in counter.most_common(k)]

def get_most_frequent_period(draws, days: int = 365, k: int = 6):
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=days)
    filtered = [(d, nums) for d, nums in draws if d >= cutoff]
    return get_most_frequent(filtered, k)

def get_weighted(draws, k: int = 6):
    counter = Counter()
    for _, nums in draws:
        counter.update(nums)
    all_nums = list(range(1, 61))
    weights = [counter[n] for n in all_nums]
    if sum(weights) == 0:
        return random.sample(all_nums, k)
    probs = [w/sum(weights) for w in weights]
    chosen = set()
    while len(chosen) < k:
        picks = random.choices(all_nums, weights=probs, k=k-len(chosen))
        chosen.update(picks)
    return sorted(chosen)

def plot_frequency(draws):
    counter = Counter()
    for _, nums in draws:
        counter.update(nums)
    numbers, frequencies = zip(*sorted(counter.items()))
    plt.bar(numbers, frequencies)
    plt.title('Frequência dos Números Sorteados')
    plt.xlabel('Números')
    plt.ylabel('Frequência')
    plt.show()

def monte_carlo_simulation(draws, simulations=10000):
    all_nums = list(range(1, 61))
    simulated_counts = Counter()
    for _ in range(simulations):
        simulated_draw = np.random.choice(all_nums, size=6, replace=False)
        simulated_counts.update(simulated_draw)
    real_counts = Counter()
    for _, nums in draws:
        real_counts.update(nums)
    
    # Retorna os 6 números mais frequentes simulados e reais
    most_simulated = simulated_counts.most_common(6)
    most_real = real_counts.most_common(6)
    return most_simulated, most_real

def calculate_correlation(draws):
    data = []
    for _, nums in draws:
        data.append([1 if i in nums else 0 for i in range(1, 61)])
    df = pd.DataFrame(data, columns=[f'Num_{i}' for i in range(1, 61)])
    correlation_matrix = df.corr()
    return correlation_matrix

def analyze_probability_distribution(draws):
    counter = Counter()
    for _, nums in draws:
        counter.update(nums)
    observed = [counter[i] for i in range(1, 61)]
    expected = [sum(observed) / 60] * 60
    chi2, p = chisquare(observed, expected)
    return chi2, p

def analyze_time_series(draws):
    dates = [d for d, _ in draws]
    frequencies = Counter(dates)
    sorted_dates = sorted(frequencies.keys())
    counts = [frequencies[date] for date in sorted_dates]
    plt.plot(sorted_dates, counts)
    plt.title('Tendência de Sorteios ao Longo do Tempo')
    plt.xlabel('Data')
    plt.ylabel('Frequência de Sorteios')
    plt.show()

def export_results(data, file_format="csv", filename="results"):
    if file_format == "csv":
        with open(f"{filename}.csv", "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Número", "Frequência"])
            writer.writerows(data)
    elif file_format == "json":
        with open(f"{filename}.json", "w") as jsonfile:
            json.dump(data, jsonfile, indent=4)
    print(f"Resultados exportados para {filename}.{file_format}")

def schedule_task():
    task_name = "MegaSenaUpdate"
    command = f"schtasks /create /tn {task_name} /tr 'python {os.path.abspath(__file__)} --update' /sc daily /st 12:00"
    subprocess.run(command, shell=True)
    print(f"Tarefa agendada com sucesso: {task_name}")

# ---------------------
# Interface de Linha de Comando
# ---------------------

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
    parser.add_argument('--export', type=str, help='Exportar resultados para CSV ou JSON')
    args = parser.parse_args()

    global DB_PATH
    if args.db_path:
        DB_PATH = args.db_path

    if args.update:
        update_db()
        sys.exit(0)

    draws = load_all_draws()
    if not draws:
        logging.error('Base vazia: execute com --update primeiro')
        sys.exit(1)

    if args.alltime:
        result = get_most_frequent(draws)
        print('Top 6 de todos os tempos:', result)
    elif args.lastyear:
        result = get_most_frequent_period(draws)
        print('Top 6 do último ano:', result)
    elif args.stat:
        result = get_weighted(draws)
        print('Conjunto estatístico:', result)
    elif args.plot:
        plot_frequency(draws)
    elif args.montecarlo:
        simulated, real = monte_carlo_simulation(draws)
        print('Simulação de Monte Carlo - Números mais frequentes:')
        print('Simulados:', simulated)
        print('Reais:', real)
    elif args.correlation:
        correlation_matrix = calculate_correlation(draws)
        print('Matriz de Correlação:', correlation_matrix)
    elif args.timeseries:
        analyze_time_series(draws)
    elif args.distribution:
        chi2, p = analyze_probability_distribution(draws)
        print(f'Chi2: {chi2}, p-valor: {p}')
    elif args.export:
        file_format = args.export.split('.')[-1]
        export_results(draws, file_format, args.export.rsplit('.', 1)[0])
    else:
        parser.print_help()

if __name__ == '__main__':
    main()

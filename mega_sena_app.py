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

def fetch_concurso(concurso: int = None) -> dict:
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
        print('Top 6 de todos os tempos:', get_most_frequent(draws))
    elif args.lastyear:
        print('Top 6 do último ano:', get_most_frequent_period(draws))
    elif args.stat:
        print('Conjunto estatístico:', get_weighted(draws))
    else:
        parser.print_help()

if __name__ == '__main__':
    main()

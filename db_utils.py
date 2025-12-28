#!/usr/bin/env python3
"""
Utilitários para gerenciamento de banco de dados SQLite.

Fornece funções para limpeza de locks, verificação de integridade e
otimização de bancos de dados.
"""

import sqlite3
import os
import logging
from typing import Tuple
from contextlib import contextmanager

# Caminhos padrão dos bancos de dados
DB_PATH = 'megasena.db'
BACKTEST_DB_PATH = 'backtest.db'

def check_db_integrity(db_path: str) -> Tuple[bool, str]:
    """
    Verifica a integridade do banco de dados SQLite.
    
    Retorna: (is_healthy, message)
    """
    if not os.path.exists(db_path):
        return False, f"Banco de dados não encontrado: {db_path}"
    
    try:
        with sqlite3.connect(db_path, timeout=20.0) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            cursor = conn.cursor()
            # Executar verificação de integridade
            cursor.execute('PRAGMA integrity_check')
            result = cursor.fetchone()

        if result and result[0] == 'ok':
            return True, "Banco de dados íntegro"
        else:
            return False, f"Problemas detectados: {result}"
    except sqlite3.DatabaseError as e:
        return False, f"Erro ao verificar banco: {e}"
    except Exception as e:
        return False, f"Erro inesperado: {e}"

def vacuum_db(db_path: str) -> Tuple[bool, str]:
    """
    Otimiza o banco de dados removendo espaço vazio.
    
    Retorna: (success, message)
    """
    if not os.path.exists(db_path):
        return False, f"Banco de dados não encontrado: {db_path}"
    
    try:
        with sqlite3.connect(db_path, timeout=20.0) as conn:
            conn.execute('VACUUM')
        return True, "Banco de dados otimizado com sucesso"
    except Exception as e:
        return False, f"Erro ao otimizar banco: {e}"

def enable_wal_mode(db_path: str) -> Tuple[bool, str]:
    """
    Ativa o modo Write-Ahead Logging (WAL) para reduzir locks.
    
    Retorna: (success, message)
    """
    if not os.path.exists(db_path):
        return False, f"Banco de dados não encontrado: {db_path}"
    
    try:
        with sqlite3.connect(db_path, timeout=20.0) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')  # Aumenta performance
            conn.execute('PRAGMA cache_size=10000')    # Maior cache
        return True, "Modo WAL ativado com sucesso"
    except Exception as e:
        return False, f"Erro ao ativar WAL: {e}"

def analyze_db(db_path: str) -> Tuple[bool, str]:
    """
    Analisa o banco para otimizar performance de queries.
    
    Retorna: (success, message)
    """
    if not os.path.exists(db_path):
        return False, f"Banco de dados não encontrado: {db_path}"
    
    try:
        with sqlite3.connect(db_path, timeout=20.0) as conn:
            conn.execute('ANALYZE')
        return True, "Análise do banco concluída"
    except Exception as e:
        return False, f"Erro ao analisar banco: {e}"

def get_db_info(db_path: str) -> dict:
    """
    Retorna informações sobre o banco de dados.
    
    Retorna: dicionário com info de tamanho, número de tabelas, etc.
    """
    if not os.path.exists(db_path):
        return {'error': f'Banco não encontrado: {db_path}'}
    
    try:
        size_bytes = os.path.getsize(db_path)
        size_mb = size_bytes / (1024 * 1024)
        
        with sqlite3.connect(db_path, timeout=20.0) as conn:
            cursor = conn.cursor()
            # Contar tabelas
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            # Contar índices
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
            index_count = cursor.fetchone()[0]
            # Informações de modo journal
            cursor.execute('PRAGMA journal_mode')
            journal_mode = cursor.fetchone()[0]

        return {
            'path': db_path,
            'size_bytes': size_bytes,
            'size_mb': f"{size_mb:.2f}",
            'table_count': table_count,
            'index_count': index_count,
            'journal_mode': journal_mode
        }
    except Exception as e:
        return {'error': f'Erro ao obter informações: {e}'}

def cleanup_databases() -> dict:
    """
    Realiza limpeza e otimização de todos os bancos do projeto.
    
    Retorna: dicionário com resultados de cada operação
    """
    databases = [
        'megasena.db',
        'user_sets.db',
        'backtest.db'
    ]
    
    results = {}
    
    for db_name in databases:
        if not os.path.exists(db_name):
            results[db_name] = {'status': 'não encontrado'}
            continue
        
        # Ativar WAL
        success, msg = enable_wal_mode(db_name)
        results[db_name] = {'wal_mode': {'success': success, 'message': msg}}
        
        # Verificar integridade
        is_healthy, msg = check_db_integrity(db_name)
        results[db_name]['integrity'] = {'healthy': is_healthy, 'message': msg}
        
        # Analisar
        success, msg = analyze_db(db_name)
        results[db_name]['analyze'] = {'success': success, 'message': msg}
        
        # Vacuum
        success, msg = vacuum_db(db_name)
        results[db_name]['vacuum'] = {'success': success, 'message': msg}
        
        # Info
        results[db_name]['info'] = get_db_info(db_name)
    
    return results

@contextmanager
def open_db(path: str, timeout: float = 20.0):
    """Context manager para abrir conexão SQLite com WAL e fechamento seguro."""
    conn = sqlite3.connect(path, timeout=timeout)
    try:
        conn.execute('PRAGMA journal_mode=WAL')
    except sqlite3.Error:
        pass
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass

def init_backtest_db(path: str = 'backtest.db') -> None:
    """
    Inicializa a base de dados para armazenar os resultados do backtest,
    criando as tabelas 'backtest_results' e 'backtest_numbers' se não existirem.
    Também realiza migração dos dados antigos para o novo esquema.
    """
    try:
        with sqlite3.connect(path, timeout=20.0) as conn:
            cursor = conn.cursor()
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
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backtest_numbers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    method TEXT NOT NULL,
                    date_tested TEXT NOT NULL,
                    generated_number INTEGER NOT NULL,
                    draw_date TEXT NOT NULL,
                    matches INTEGER NOT NULL
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backtest_numbers_method ON backtest_numbers(method)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backtest_numbers_generated_number ON backtest_numbers(generated_number)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_backtest_numbers_matches ON backtest_numbers(matches)')
            conn.commit()
            # Migração automática
            cursor.execute('SELECT COUNT(1) FROM backtest_numbers')
            if cursor.fetchone()[0] == 0:
                cursor.execute('SELECT id FROM backtest_results LIMIT 1')
                if cursor.fetchone():
                    logging.info('Iniciando migração de dados: backtest_results -> backtest_numbers')
                    _migrate_backtest_results_to_numbers(conn)
    except sqlite3.Error as e:
        logging.error(f"Erro ao inicializar o banco de dados de backtest: {e}")

def _migrate_backtest_results_to_numbers(conn: sqlite3.Connection) -> None:
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT method, date_tested, generated_numbers, draw_date, matches FROM backtest_results')
        rows = cursor.fetchall()
        inserts = []
        for method, date_tested, generated_numbers_str, draw_date, matches in rows:
            try:
                numbers = [int(n) for n in generated_numbers_str.split(',') if n.strip()]
                for num in numbers:
                    inserts.append((method, date_tested, num, draw_date, matches))
            except Exception:
                logging.warning(f'Ignorando row inválida durante migração: {generated_numbers_str}')
                continue
        if inserts:
            cursor.executemany('''
                INSERT INTO backtest_numbers (method, date_tested, generated_number, draw_date, matches)
                VALUES (?, ?, ?, ?, ?)
            ''', inserts)
            conn.commit()
            logging.info(f'Migração concluída: {len(inserts)} linhas inseridas em backtest_numbers')
    except sqlite3.Error as e:
        logging.error(f'Erro na migração de backtest: {e}')

if __name__ == '__main__':
    # Configurar logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("\n" + "="*60)
    print("GERENCIADOR DE BANCO DE DADOS - MEGA-SENA ANALYZER")
    print("="*60 + "\n")
    
    # Executar limpeza
    results = cleanup_databases()
    
    # Exibir resultados
    for db_name, operations in results.items():
        print(f"\n📊 {db_name}:")
        for operation, result in operations.items():
            if operation == 'info':
                print(f"  ℹ️  Informações:")
                for key, value in result.items():
                    print(f"     {key}: {value}")
            else:
                if isinstance(result, dict):
                    status = "✅" if result.get('success') else "❌"
                    print(f"  {status} {operation}: {result.get('message', 'OK')}")
                else:
                    print(f"  {operation}: {result}")
    
    print("\n" + "="*60)
    print("✅ Limpeza e otimização concluída!")
    print("="*60 + "\n")

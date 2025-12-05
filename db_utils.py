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

def check_db_integrity(db_path: str) -> Tuple[bool, str]:
    """
    Verifica a integridade do banco de dados SQLite.
    
    Retorna: (is_healthy, message)
    """
    if not os.path.exists(db_path):
        return False, f"Banco de dados não encontrado: {db_path}"
    
    try:
        conn = sqlite3.connect(db_path, timeout=20.0)
        conn.execute('PRAGMA journal_mode=WAL')
        cursor = conn.cursor()
        
        # Executar verificação de integridade
        cursor.execute('PRAGMA integrity_check')
        result = cursor.fetchone()
        conn.close()
        
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
        conn = sqlite3.connect(db_path, timeout=20.0)
        conn.execute('VACUUM')
        conn.close()
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
        conn = sqlite3.connect(db_path, timeout=20.0)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')  # Aumenta performance
        conn.execute('PRAGMA cache_size=10000')    # Maior cache
        conn.close()
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
        conn = sqlite3.connect(db_path, timeout=20.0)
        conn.execute('ANALYZE')
        conn.close()
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
        
        conn = sqlite3.connect(db_path, timeout=20.0)
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
        
        conn.close()
        
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

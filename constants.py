"""Constantes e configuração básica do projeto.
Move as definições de caminho de DB e constantes numéricas para um módulo separado
para evitar import circular quando modularizarmos outras partes.
"""
import os
import logging

# Tentativa de usar arquivo de configuração externo (opcional)
try:
    from config import get_config, get_db_path
    try:
        _config = get_config()
        DB_PATH = os.getenv('MEGASENA_DB_PATH', get_db_path())
    except Exception:
        DB_PATH = os.getenv('MEGASENA_DB_PATH', 'megasena.db')
except Exception:
    DB_PATH = os.getenv('MEGASENA_DB_PATH', 'megasena.db')

API_BASE = 'https://loteriascaixa-api.herokuapp.com/api/megasena'
USER_SETS_DB_PATH = os.getenv('MEGASENA_USER_SETS_DB_PATH', 'user_sets.db')
BACKTEST_DB_PATH = os.getenv('MEGASENA_BACKTEST_DB_PATH', 'backtest.db')

# Números padrão
NUM_DEZENAS = 6
MAX_NUM_MEGA_SENA = 60

# Expose logger for modules to use
logger = logging.getLogger('mega_sena')

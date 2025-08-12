#!/usr/bin/env python3
"""
Sistema de Logs Avançado para Mega-Sena Analyzer

Configura logging com rotação de arquivos e diferentes níveis.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Optional

def setup_enhanced_logging(log_level: str = 'INFO', 
                          console_level: str = 'WARNING',
                          max_file_size: int = 5 * 1024 * 1024,  # 5MB
                          backup_count: int = 5) -> logging.Logger:
    """
    Configura sistema de logs avançado com rotação
    
    Args:
        log_level: Nível de log para arquivo (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console_level: Nível de log para console
        max_file_size: Tamanho máximo do arquivo de log em bytes
        backup_count: Número de arquivos de backup a manter
    
    Returns:
        Logger configurado
    """
    
    # Criar diretório de logs
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # Configurar formatação detalhada
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Formatação simples para console
    simple_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    
    # Logger principal
    logger = logging.getLogger('mega_sena')
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Limpar handlers existentes
    logger.handlers.clear()
    
    # Handler para arquivo rotativo - log geral
    general_file_handler = logging.handlers.RotatingFileHandler(
        f'{log_dir}/mega_sena.log',
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
    general_file_handler.setFormatter(detailed_formatter)
    general_file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.addHandler(general_file_handler)
    
    # Handler para arquivo de erros
    error_file_handler = logging.handlers.RotatingFileHandler(
        f'{log_dir}/mega_sena_errors.log',
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
    error_file_handler.setFormatter(detailed_formatter)
    error_file_handler.setLevel(logging.ERROR)
    logger.addHandler(error_file_handler)
    
    # Handler para console (apenas avisos e erros por padrão)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, console_level.upper(), logging.WARNING))
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)
    
    # Logger específico para ações da GUI
    gui_logger = logging.getLogger('mega_sena.gui')
    gui_file_handler = logging.handlers.RotatingFileHandler(
        f'{log_dir}/gui_actions.log',
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
    gui_file_handler.setFormatter(detailed_formatter)
    gui_logger.addHandler(gui_file_handler)
    
    # Logger para análises
    analysis_logger = logging.getLogger('mega_sena.analysis')
    analysis_file_handler = logging.handlers.RotatingFileHandler(
        f'{log_dir}/analysis.log',
        maxBytes=max_file_size,
        backupCount=backup_count,
        encoding='utf-8'
    )
    analysis_file_handler.setFormatter(detailed_formatter)
    analysis_logger.addHandler(analysis_file_handler)
    
    # Log inicial
    logger.info("="*50)
    logger.info(f"Mega-Sena Analyzer iniciado em {datetime.now()}")
    logger.info(f"Nível de log: {log_level}")
    logger.info(f"Diretório de logs: {os.path.abspath(log_dir)}")
    logger.info("="*50)
    
    return logger

def get_logger(name: str = 'mega_sena') -> logging.Logger:
    """Retorna logger configurado"""
    return logging.getLogger(name)

def log_function_call(func_name: str, args: tuple = (), kwargs: dict = {}) -> None:
    """Log de chamada de função para debugging"""
    logger = get_logger('mega_sena.debug')
    args_str = ', '.join([str(arg) for arg in args])
    kwargs_str = ', '.join([f"{k}={v}" for k, v in kwargs.items()])
    all_args = ', '.join(filter(None, [args_str, kwargs_str]))
    logger.debug(f"Chamando {func_name}({all_args})")

def log_performance(func_name: str, duration: float, details: str = "") -> None:
    """Log de performance de função"""
    logger = get_logger('mega_sena.performance')
    logger.info(f"Performance - {func_name}: {duration:.3f}s {details}")

def log_user_action(action: str, details: str = "", user_id: str = "default") -> None:
    """Log de ação do usuário"""
    logger = get_logger('mega_sena.gui')
    logger.info(f"Usuário {user_id} - {action}: {details}")

def log_analysis_result(analysis_type: str, result_count: int, duration: float = 0) -> None:
    """Log de resultado de análise"""
    logger = get_logger('mega_sena.analysis')
    duration_str = f" ({duration:.3f}s)" if duration > 0 else ""
    logger.info(f"Análise {analysis_type} concluída: {result_count} resultados{duration_str}")

def log_error_with_context(error: Exception, context: str = "", extra_data: dict = {}) -> None:
    """Log de erro com contexto adicional"""
    logger = get_logger('mega_sena')
    error_msg = f"Erro em {context}: {str(error)}"
    if extra_data:
        error_msg += f" | Dados: {extra_data}"
    logger.error(error_msg, exc_info=True)

def cleanup_old_logs(days_to_keep: int = 30) -> None:
    """Remove logs antigos"""
    import glob
    import time
    
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        return
    
    cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
    
    for log_file in glob.glob(f"{log_dir}/*.log*"):
        try:
            if os.path.getmtime(log_file) < cutoff_time:
                os.remove(log_file)
                print(f"Log antigo removido: {log_file}")
        except OSError:
            pass

# Decorator para log automático de funções
def log_function(logger_name: str = 'mega_sena'):
    """Decorator para log automático de entrada e saída de função"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name)
            func_name = func.__name__

            # Log entrada
            logger.debug(f"Iniciando {func_name}")

            try:
                result = func(*args, **kwargs)
                # Log saída
                logger.debug(f"Finalizando {func_name}")
                return result
            except Exception as e:
                logger.error(f"Erro ao executar a função {func_name}: {e}", exc_info=True)
                raise

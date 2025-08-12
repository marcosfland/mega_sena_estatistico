#!/usr/bin/env python3
"""
Sistema de Configuração para Mega-Sena Analyzer

Gerencia configurações do aplicativo através de arquivo INI.
"""

import configparser
import os
import logging
from typing import Dict, Any, Optional

class Config:
    """Classe para gerenciar configurações do aplicativo"""
    
    def __init__(self, config_file: str = 'mega_sena_config.ini'):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        self.load_config()
    
    def load_config(self) -> None:
        """Carrega configurações do arquivo ou cria configurações padrão"""
        if os.path.exists(self.config_file):
            try:
                self.config.read(self.config_file, encoding='utf-8')
                logging.info(f"Configurações carregadas de {self.config_file}")
            except Exception as e:
                logging.warning(f"Erro ao carregar configurações: {e}. Usando padrões.")
                self.create_default_config()
        else:
            self.create_default_config()
    
    def create_default_config(self) -> None:
        """Cria configurações padrão"""
        self.config['DATABASE'] = {
            'path': 'megasena.db',
            'backup_enabled': 'true',
            'max_backups': '5',
            'cache_enabled': 'true'
        }
        
        self.config['ANALYSIS'] = {
            'default_period_days': '365',
            'monte_carlo_simulations': '10000',
            'prediction_recent_weight': '0.4',
            'prediction_frequency_weight': '0.3',
            'prediction_gap_weight': '0.2'
        }
        
        self.config['GUI'] = {
            'theme': 'clam',
            'auto_update': 'true',
            'notifications': 'true',
            'window_width': '700',
            'window_height': '950'
        }
        
        self.config['WEB'] = {
            'port': '5000',
            'host': '127.0.0.1',
            'debug': 'false'
        }
        
        self.config['EXPORT'] = {
            'default_format': 'csv',
            'auto_open_folder': 'true',
            'include_headers': 'true'
        }
        
        self.save_config()
        logging.info("Configurações padrão criadas")
    
    def save_config(self) -> None:
        """Salva configurações no arquivo"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            logging.info(f"Configurações salvas em {self.config_file}")
        except Exception as e:
            logging.error(f"Erro ao salvar configurações: {e}")
    
    def get(self, section: str, key: str, fallback: Any = None) -> str:
        """Obtém valor de configuração"""
        try:
            return self.config.get(section, key, fallback=str(fallback) if fallback is not None else "")
        except (configparser.NoSectionError, configparser.NoOptionError):
            return str(fallback) if fallback is not None else ""
    
    def getint(self, section: str, key: str, fallback: int = 0) -> int:
        """Obtém valor inteiro de configuração"""
        try:
            return self.config.getint(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def getfloat(self, section: str, key: str, fallback: float = 0.0) -> float:
        """Obtém valor float de configuração"""
        try:
            return self.config.getfloat(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def getboolean(self, section: str, key: str, fallback: bool = False) -> bool:
        """Obtém valor booleano de configuração"""
        try:
            return self.config.getboolean(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def set(self, section: str, key: str, value: Any) -> None:
        """Define valor de configuração"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, key, str(value))
    
    def get_all_settings(self) -> Dict[str, Dict[str, str]]:
        """Retorna todas as configurações como dicionário"""
        settings = {}
        for section_name in self.config.sections():
            settings[section_name] = dict(self.config[section_name])
        return settings
    
    def reset_to_defaults(self) -> None:
        """Reseta todas as configurações para os valores padrão"""
        self.config.clear()
        self.create_default_config()
        logging.info("Configurações resetadas para valores padrão")

# Instância global de configuração
app_config = Config()

def get_config() -> Config:
    """Retorna a instância global de configuração"""
    return app_config

# Funções de conveniência para acessar configurações comuns
def get_db_path() -> str:
    """Retorna o caminho do banco de dados"""
    return app_config.get('DATABASE', 'path', 'megasena.db')

def get_monte_carlo_simulations() -> int:
    """Retorna o número de simulações Monte Carlo"""
    return app_config.getint('ANALYSIS', 'monte_carlo_simulations', 10000)

def get_gui_theme() -> str:
    """Retorna o tema da GUI"""
    return app_config.get('GUI', 'theme', 'clam')

def get_web_port() -> int:
    """Retorna a porta do servidor web"""
    return app_config.getint('WEB', 'port', 5000)

def is_cache_enabled() -> bool:
    """Verifica se o cache está habilitado"""
    return app_config.getboolean('DATABASE', 'cache_enabled', True)

def is_auto_update_enabled() -> bool:
    """Verifica se a atualização automática está habilitada"""
    return app_config.getboolean('GUI', 'auto_update', True)

if __name__ == "__main__":
    # Teste das configurações
    config = get_config()
    print("Configurações atuais:")
    for section, settings in config.get_all_settings().items():
        print(f"\n[{section}]")
        for key, value in settings.items():
            print(f"  {key} = {value}")

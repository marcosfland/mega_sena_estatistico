import sys
import os
import subprocess
from cx_Freeze import setup, Executable

def get_git_version():
    """Obtém versão do Git se disponível"""
    try:
        # Tenta obter a tag mais recente
        result = subprocess.run(['git', 'describe', '--tags', '--abbrev=0'], 
                              capture_output=True, text=True, cwd=os.path.dirname(__file__))
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    
    # Fallback para versão manual
    return "1.3.0"

def get_build_info():
    """Obtém informações de build"""
    try:
        # Hash do commit atual
        result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            commit_hash = result.stdout.strip()
            return f"build-{commit_hash}"
    except:
        pass
    
    from datetime import datetime
    return f"build-{datetime.now().strftime('%Y%m%d')}"

VERSION = get_git_version()
BUILD_INFO = get_build_info()
FULL_VERSION = f"{VERSION}-{BUILD_INFO}"

print(f"🔨 Versão detectada: {FULL_VERSION}")

# Nome do arquivo principal do seu projeto
main_script = "main.py"

# Dependências adicionais (se houver)
build_exe_options = {
    "packages": [],
    "excludes": [],
    "include_files": []
}

# Informações do executável
setup(
    name="MegaSenaEstatistico",
    version="1.0",
    description="Ferramenta estatística para Mega Sena",
    options={"build_exe": build_exe_options},
    executables=[Executable(main_script, base=None)]
)

# Para gerar o executável, execute no terminal:
# python build_executable.py build
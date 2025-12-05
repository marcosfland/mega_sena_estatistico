#!/usr/bin/env python3
"""
Demonstração de Multiple Backtest Execution
Mostra diferentes cenários de uso da nova funcionalidade
"""

import subprocess
import sys

def run_command(cmd):
    """Executa um comando e exibe resultado"""
    print(f"\n{'='*70}")
    print(f"Executando: {cmd}")
    print(f"{'='*70}")
    result = subprocess.run(cmd, shell=True, capture_output=False, text=True)
    return result.returncode

def main():
    """Demonstra diferentes usos da funcionalidade"""
    
    print("\n" + "="*70)
    print("DEMONSTRAÇÃO: Multiple Backtest Execution")
    print("="*70)
    
    # Teste 1: Backtests simples (default)
    print("\n\n[TESTE 1] Execução simples com default (weighted, 1x)")
    print("-" * 70)
    run_command("python mega_sena_app.py --backtest")
    
    # Teste 2: Alltime 1x
    print("\n\n[TESTE 2] Método alltime com 1 execução")
    print("-" * 70)
    run_command("python mega_sena_app.py --backtest alltime --backtest-times 1")
    
    # Teste 3: Weighted 3x
    print("\n\n[TESTE 3] Método weighted com 3 execuções")
    print("-" * 70)
    run_command("python mega_sena_app.py --backtest weighted --backtest-times 3")
    
    # Teste 4: Lastyear 2x
    print("\n\n[TESTE 4] Método lastyear com 2 execuções")
    print("-" * 70)
    run_command("python mega_sena_app.py --backtest lastyear --backtest-times 2")
    
    print("\n\n" + "="*70)
    print("DEMONSTRAÇÃO CONCLUÍDA")
    print("="*70)
    
    print("""
    
📊 RESUMO DOS TESTES:

✓ Teste 1: Default (weighted, 1x) - Uso mais simples
✓ Teste 2: Alltime (determinístico) - Para validação
✓ Teste 3: Weighted (3 execuções) - Exemplo de consolidação
✓ Teste 4: Lastyear (2 execuções) - Teste de múltiplos

🎯 OBSERVAÇÕES:

1. Alltime deve gerar os MESMOS números em cada execução
2. Weighted deve gerar números DIFERENTES (variável)
3. Lastyear deve ser mais próximo ao alltime (tendências recentes)
4. Consolidação mostra números mais frequentes ao longo das execuções

📈 PRÓXIMOS PASSOS:

- Use esses comandos em seu workflow de análise
- Compare os resultados com sorteios reais
- Experimente com diferentes quantidades (--backtest-times 5, 10, 20)
- Estude padrões na consolidação de números

💡 DICA:

Para análise estatística mais robusta, execute:
  python mega_sena_app.py --backtest weighted --backtest-times 20
  
Isso executará 20 backtests e consolidará os números mais frequentes!
    """)

if __name__ == "__main__":
    main()

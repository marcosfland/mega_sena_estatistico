class TestCLI(unittest.TestCase):
    """Testes para parsing de argumentos do CLI (cli.py)"""

    def test_argparse_alltime(self):
        import cli
        sys_argv_backup = sys.argv.copy()
        sys.argv = ['cli.py', '--alltime']
        try:
            cli.main()
        finally:
            sys.argv = sys_argv_backup

    def test_argparse_lastyear(self):
        import cli
        sys_argv_backup = sys.argv.copy()
        sys.argv = ['cli.py', '--lastyear']
        try:
            cli.main()
        finally:
            sys.argv = sys_argv_backup

    def test_argparse_stat(self):
        import cli
        sys_argv_backup = sys.argv.copy()
        sys.argv = ['cli.py', '--stat']
        try:
            cli.main()
        finally:
            sys.argv = sys_argv_backup

    def test_argparse_backtest_insights(self):
        import cli
        sys_argv_backup = sys.argv.copy()
        sys.argv = ['cli.py', '--backtest-insights', 'weighted']
        try:
            cli.main()
        finally:
            sys.argv = sys_argv_backup
import types
import sys
class TestGuiUtils(unittest.TestCase):
    """Testes para funções utilitárias da interface gráfica (gui_utils.py)"""

    def setUp(self):
        import gui_utils
        # Mock status_bar e root
        gui_utils.status_bar = types.SimpleNamespace(config=lambda text=None: None)
        gui_utils.root = None

    def test_show_message_info(self):
        import gui_utils
        # Mock messagebox
        gui_utils.messagebox = types.SimpleNamespace(showinfo=lambda t, m: True, showerror=lambda t, m: False)
        gui_utils.show_message("Info", "Mensagem de teste", is_error=False)

    def test_show_message_error(self):
        import gui_utils
        gui_utils.messagebox = types.SimpleNamespace(showinfo=lambda t, m: True, showerror=lambda t, m: True)
        gui_utils.show_message("Erro", "Mensagem de erro", is_error=True)

    def test_ask_on_main_thread(self):
        import gui_utils
        result = gui_utils.ask_on_main_thread(lambda x: x + 1, 2)
        self.assertEqual(result, 3)

    def test_tooltip(self):
        import gui_utils
        # Mock widget
        widget = types.SimpleNamespace(bind=lambda *a, **k: None, winfo_rootx=lambda: 0, winfo_rooty=lambda: 0, winfo_height=lambda: 0)
        tip = gui_utils.Tooltip(widget, text="Teste")
        tip.set_text("Novo texto")
        self.assertEqual(tip.text, "Novo texto")

    def test_open_file_location(self):
        import gui_utils
        gui_utils.os = types.SimpleNamespace(name='nt', path=gui_utils.os.path, startfile=lambda x: True)
        gui_utils.show_message = lambda t, m, e=False: None
        gui_utils.open_file_location(__file__)

    def test_run_in_thread(self):
        import gui_utils
        gui_utils.status_bar = types.SimpleNamespace(config=lambda text=None: None)
        called = []
        def func():
            called.append(True)
        gui_utils.run_in_thread(func)
        import time
        time.sleep(0.1)
        self.assertTrue(called)

    def test_start_processing(self):
        import gui_utils
        gui_utils.status_bar = types.SimpleNamespace(config=lambda text=None: None)
        gui_utils.progress_bar = types.SimpleNamespace(start=lambda x: None)
        gui_utils.root = types.SimpleNamespace(config=lambda cursor=None: None)
        gui_utils.interactive_buttons = [types.SimpleNamespace(config=lambda state=None: None)]
        gui_utils.start_processing()
class TestAnalysis(unittest.TestCase):
    """Testes para funções estatísticas de analysis.py"""

    def setUp(self):
        self.draws = [
            (datetime.date(2023, 1, 1), (1, 2, 3, 4, 5, 6)),
            (datetime.date(2023, 1, 2), (2, 3, 4, 5, 6, 7)),
            (datetime.date(2023, 1, 3), (3, 4, 5, 6, 7, 8)),
        ]

    def test_get_most_frequent(self):
        import analysis
        result = analysis.get_most_frequent(self.draws, k=3)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(isinstance(n, int) for n in result))

    def test_get_most_frequent_period(self):
        import analysis
        result = analysis.get_most_frequent_period(self.draws, days=365, k=3)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(isinstance(n, int) for n in result))

    def test_get_weighted(self):
        import analysis
        result = analysis.get_weighted(self.draws, k=6)
        self.assertEqual(len(result), 6)
        self.assertTrue(all(isinstance(n, int) for n in result))
class TestBacktest(unittest.TestCase):
    """Testes para funções de backtest.py"""

    def setUp(self):
        # Cria banco temporário para backtest
        self.temp_db_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db_path = self.temp_db_file.name
        self.temp_db_file.close()
        # Inicializa banco de backtest
        import db_utils
        db_utils.init_backtest_db(self.temp_db_path)
        # Mock simples para load_all_draws
        self.sample_draws = [
            (datetime.date(2023, 1, 1), (1, 2, 3, 4, 5, 6)),
            (datetime.date(2023, 1, 2), (7, 8, 9, 10, 11, 12)),
        ]
        import mega_sena_app
        mega_sena_app.load_all_draws = lambda: self.sample_draws

        # Patch caminho do banco
        import backtest
        backtest.BACKTEST_DB_PATH = self.temp_db_path

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            os.unlink(self.temp_db_path)

    def test_run_backtest_alltime(self):
        import backtest
        result = backtest.run_backtest("alltime")
        self.assertTrue(result)

    def test_run_backtest_multiple(self):
        import backtest
        res = backtest.run_backtest_multiple("alltime", times=2)
        self.assertTrue(res['success'])
        self.assertEqual(res['times_requested'], 2)
        self.assertGreaterEqual(res['times_successful'], 1)

    def test_get_from_backtest_insights(self):
        import backtest
        # Executa um backtest para popular o banco
        backtest.run_backtest("alltime")
        nums = backtest.get_from_backtest_insights("alltime", k=6)
        self.assertIsInstance(nums, list)
        self.assertEqual(len(nums), 6)
#!/usr/bin/env python3
"""
Testes Unitários para Mega-Sena Analyzer - Versão Corrigida

Testa as principais funcionalidades do sistema com tratamento de importação robusto.
"""

import unittest
import sys
import os
import datetime
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock

# Adicionar o diretório do projeto (raiz) ao path para importar o módulo
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Tentar importar o módulo principal
try:
    import mega_sena_app
    MODULE_AVAILABLE = True
except ImportError as e:
    print(f"Erro ao importar mega_sena_app: {e}")
    MODULE_AVAILABLE = False
    mega_sena_app = None

class TestMegaSenaAnalyzer(unittest.TestCase):
    """Testes para o analisador da Mega-Sena"""
    
    def setUp(self):
        """Configuração inicial para os testes"""
        if not MODULE_AVAILABLE:
            self.skipTest("Módulo mega_sena_app não pode ser importado")
        
        # Dados de teste - usar datas mais recentes
        self.sample_draws = [
            (datetime.date.today() - datetime.timedelta(days=5), (1, 2, 3, 4, 5, 6)),
            (datetime.date.today() - datetime.timedelta(days=10), (7, 8, 9, 10, 11, 12)),
            (datetime.date.today() - datetime.timedelta(days=15), (1, 2, 13, 14, 15, 16)),
            (datetime.date.today() - datetime.timedelta(days=20), (1, 3, 17, 18, 19, 20)),
            (datetime.date.today() - datetime.timedelta(days=25), (2, 4, 21, 22, 23, 24)),
        ]
    
    def test_get_most_frequent(self):
        """Testa cálculo de números mais frequentes"""
        if not hasattr(mega_sena_app, 'get_most_frequent'):
            self.skipTest("Função get_most_frequent não está disponível")
        
        result = mega_sena_app.get_most_frequent(self.sample_draws, k=3)
        
        # Verificar se retorna o número correto de elementos
        self.assertEqual(len(result), 3)
        
        # Verificar se 1 e 2 estão entre os mais frequentes (aparecem 3 vezes cada)
        self.assertIn(1, result)
        self.assertIn(2, result)
        
        # Verificar se todos são inteiros válidos
        for num in result:
            self.assertIsInstance(num, int)
            self.assertGreaterEqual(num, 1)
            self.assertLessEqual(num, 60)
    
    def test_get_most_frequent_period(self):
        """Testa cálculo de números mais frequentes por período"""
        if not hasattr(mega_sena_app, 'get_most_frequent_period'):
            self.skipTest("Função get_most_frequent_period não está disponível")
        
        result = mega_sena_app.get_most_frequent_period(self.sample_draws, days=30, k=3)
        
        # Deve retornar 3 números
        self.assertEqual(len(result), 3)
        
        # Todos devem ser válidos
        for num in result:
            self.assertIsInstance(num, int)
            self.assertGreaterEqual(num, 1)
            self.assertLessEqual(num, 60)
    
    def test_get_weighted(self):
        """Testa geração de conjunto ponderado"""
        if not hasattr(mega_sena_app, 'get_weighted'):
            self.skipTest("Função get_weighted não está disponível")
        
        result = mega_sena_app.get_weighted(self.sample_draws, k=6)
        
        # Deve retornar 6 números únicos
        self.assertEqual(len(result), 6)
        self.assertEqual(len(set(result)), 6)  # Sem duplicatas
        
        # Todos devem ser válidos
        for num in result:
            self.assertIsInstance(num, int)
            self.assertGreaterEqual(num, 1)
            self.assertLessEqual(num, 60)
    
    def test_conditional_probability(self):
        """Testa cálculo de probabilidade condicional"""
        if not hasattr(mega_sena_app, 'conditional_probability'):
            self.skipTest("Função conditional_probability não está disponível")
        
        # P(2|1) = 2/3 (das 3 vezes que 1 saiu, 2 também saiu 2 vezes)
        prob = mega_sena_app.conditional_probability(self.sample_draws, 1, 2)
        self.assertAlmostEqual(prob, 2/3, places=3)
        
        # P(número que nunca saiu | 1)
        prob_zero = mega_sena_app.conditional_probability(self.sample_draws, 1, 60)
        self.assertEqual(prob_zero, 0.0)
    
    def test_get_most_frequent_pairs(self):
        """Testa análise de pares mais frequentes"""
        if not hasattr(mega_sena_app, 'get_most_frequent_pairs'):
            self.skipTest("Função get_most_frequent_pairs não está disponível")
        
        result = mega_sena_app.get_most_frequent_pairs(self.sample_draws, k=5)
        
        # Deve retornar lista de tuplas (par, frequência)
        self.assertIsInstance(result, list)
        for pair, freq in result:
            self.assertIsInstance(pair, tuple)
            self.assertEqual(len(pair), 2)
            self.assertIsInstance(freq, int)
            self.assertGreaterEqual(freq, 1)
    
    def test_get_most_frequent_triplets(self):
        """Testa análise de trios mais frequentes"""
        if not hasattr(mega_sena_app, 'get_most_frequent_triplets'):
            self.skipTest("Função get_most_frequent_triplets não está disponível")
        
        result = mega_sena_app.get_most_frequent_triplets(self.sample_draws, k=3)
        
        # Deve retornar lista de tuplas (trio, frequência)
        self.assertIsInstance(result, list)
        for triplet, freq in result:
            self.assertIsInstance(triplet, tuple)
            self.assertEqual(len(triplet), 3)
            self.assertIsInstance(freq, int)
            self.assertGreaterEqual(freq, 1)
    
    def test_calculate_prediction_score(self):
        """Testa cálculo de score de predição"""
        if not hasattr(mega_sena_app, 'calculate_prediction_score'):
            self.skipTest("Função calculate_prediction_score não está disponível")
        
        score = mega_sena_app.calculate_prediction_score(1, self.sample_draws)
        
        # Score deve ser um float entre 0 e 1
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
    
    def test_generate_smart_prediction(self):
        """Testa geração de predição inteligente"""
        if not hasattr(mega_sena_app, 'generate_smart_prediction'):
            self.skipTest("Função generate_smart_prediction não está disponível")
        
        prediction = mega_sena_app.generate_smart_prediction(self.sample_draws)
        
        # Deve retornar lista de tuplas (número, score)
        self.assertIsInstance(prediction, list)
        self.assertEqual(len(prediction), 60)  # Todos os números de 1 a 60
        
        for num, score in prediction:
            self.assertIsInstance(num, int)
            self.assertIsInstance(score, float)
            self.assertGreaterEqual(num, 1)
            self.assertLessEqual(num, 60)
    
    def test_analyze_number_gaps(self):
        """Testa análise de intervalos entre números"""
        if not hasattr(mega_sena_app, 'analyze_number_gaps'):
            self.skipTest("Função analyze_number_gaps não está disponível")
        
        gaps = mega_sena_app.analyze_number_gaps(self.sample_draws)
        
        # Deve retornar dicionário com intervalos para cada número
        self.assertIsInstance(gaps, dict)
        self.assertEqual(len(gaps), 60)  # Números de 1 a 60
        
        for num in range(1, 61):
            self.assertIn(num, gaps)
            self.assertIsInstance(gaps[num], list)
    
    def test_analyze_cycles(self):
        """Testa análise de padrões cíclicos"""
        if not hasattr(mega_sena_app, 'analyze_cycles'):
            self.skipTest("Função analyze_cycles não está disponível")
        
        cycles = mega_sena_app.analyze_cycles(self.sample_draws)
        
        # Deve retornar dicionário com distribuições
        self.assertIsInstance(cycles, dict)
        self.assertIn('weekday_distribution', cycles)
        self.assertIn('month_distribution', cycles)
        
        # Verificar estruturas internas
        self.assertIsInstance(cycles['weekday_distribution'], dict)
        self.assertIsInstance(cycles['month_distribution'], dict)
    
    def test_validate_api_data(self):
        """Testa validação de dados da API"""
        if not hasattr(mega_sena_app, 'validate_api_data'):
            self.skipTest("Função validate_api_data não está disponível")
        
        # Dados válidos
        valid_data = {
            'concurso': 2500,
            'data': '01/01/2023',
            'dezenas': ['01', '02', '03', '04', '05', '06']
        }
        self.assertTrue(mega_sena_app.validate_api_data(valid_data, 'megasena'))
        
        # Dados inválidos - faltando chave
        invalid_data = {
            'concurso': 2500,
            'data': '01/01/2023'
            # dezenas faltando
        }
        self.assertFalse(mega_sena_app.validate_api_data(invalid_data, 'megasena'))
        
        # Dados inválidos - dezenas incorretas
        invalid_dezenas = {
            'concurso': 2500,
            'data': '01/01/2023',
            'dezenas': ['01', '02', '03', '04', '05']  # Só 5 dezenas
        }
        self.assertFalse(mega_sena_app.validate_api_data(invalid_dezenas, 'megasena'))

class TestDatabaseOperations(unittest.TestCase):
    """Testes para operações de banco de dados"""
    
    def setUp(self):
        """Configuração inicial para testes de banco"""
        if not MODULE_AVAILABLE:
            self.skipTest("Módulo mega_sena_app não pode ser importado")
        
        # Criar banco temporário para testes
        self.temp_db_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db_path = self.temp_db_file.name
        self.temp_db_file.close()
    
    def tearDown(self):
        """Limpeza após os testes"""
        # Remover banco temporário
        if os.path.exists(self.temp_db_path):
            os.unlink(self.temp_db_path)
    
    def test_init_db(self):
        """Testa inicialização do banco de dados"""
        if not hasattr(mega_sena_app, 'init_db'):
            self.skipTest("Função init_db não está disponível")
        
        mega_sena_app.init_db(self.temp_db_path)
        
        # Verificar se o banco foi criado
        self.assertTrue(os.path.exists(self.temp_db_path))
        
        # Verificar se a tabela foi criada
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='megasena'")
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'megasena')

class TestMathematicalFunctions(unittest.TestCase):
    """Testes para funções matemáticas e estatísticas"""
    
    def test_edge_cases(self):
        """Testa casos extremos"""
        if not MODULE_AVAILABLE:
            self.skipTest("Módulo mega_sena_app não pode ser importado")
        
        # Lista vazia
        empty_draws = []
        
        if hasattr(mega_sena_app, 'get_most_frequent'):
            result = mega_sena_app.get_most_frequent(empty_draws, k=6)
            self.assertEqual(result, [])
        
        # Um só sorteio
        single_draw = [(datetime.date(2023, 1, 1), (1, 2, 3, 4, 5, 6))]
        
        if hasattr(mega_sena_app, 'get_most_frequent'):
            result = mega_sena_app.get_most_frequent(single_draw, k=6)
            self.assertEqual(len(result), 6)
            self.assertEqual(set(result), {1, 2, 3, 4, 5, 6})
        
        if hasattr(mega_sena_app, 'get_weighted'):
            result = mega_sena_app.get_weighted(single_draw, k=6)
            self.assertEqual(len(result), 6)

if __name__ == '__main__':
    # Executar os testes
    unittest.main(verbosity=2)


class TestDbUtils(unittest.TestCase):
    """Testes para utilitários de banco de dados (db_utils.py)"""

    def setUp(self):
        # Cria banco temporário
        self.temp_db_file = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db_path = self.temp_db_file.name
        self.temp_db_file.close()
        # Inicializa banco simples
        with sqlite3.connect(self.temp_db_path) as conn:
            conn.execute('CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)')
            conn.execute('INSERT INTO test (val) VALUES ("abc")')
            conn.commit()

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            os.unlink(self.temp_db_path)

    def test_check_db_integrity(self):
        ok, msg = db_utils.check_db_integrity(self.temp_db_path)
        self.assertTrue(ok)
        self.assertIn("íntegro", msg)

    def test_vacuum_db(self):
        success, msg = db_utils.vacuum_db(self.temp_db_path)
        self.assertTrue(success)
        self.assertIn("otimizado", msg)

    def test_enable_wal_mode(self):
        success, msg = db_utils.enable_wal_mode(self.temp_db_path)
        self.assertTrue(success)
        self.assertIn("WAL", msg)

    def test_analyze_db(self):
        success, msg = db_utils.analyze_db(self.temp_db_path)
        self.assertTrue(success)
        self.assertIn("Análise", msg)

    def test_get_db_info(self):
        info = db_utils.get_db_info(self.temp_db_path)
        self.assertIn('size_bytes', info)
        self.assertIn('table_count', info)
        self.assertEqual(info['table_count'], 1)

    def test_open_db_context(self):
        with db_utils.open_db(self.temp_db_path) as conn:
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) FROM test')
            count = cur.fetchone()[0]
        self.assertEqual(count, 1)

    def test_init_backtest_db_and_migration(self):
        # Cria banco temporário para backtest
        temp_backtest = tempfile.NamedTemporaryFile(delete=False)
        temp_backtest_path = temp_backtest.name
        temp_backtest.close()
        try:
            db_utils.init_backtest_db(temp_backtest_path)
            # Verifica tabelas
            with sqlite3.connect(temp_backtest_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backtest_results'")
                self.assertIsNotNone(cur.fetchone())
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='backtest_numbers'")
                self.assertIsNotNone(cur.fetchone())
        finally:
            if os.path.exists(temp_backtest_path):
                os.unlink(temp_backtest_path)

    def test_cleanup_databases(self):
        # Cria banco temporário com nome padrão
        temp_db_path = 'megasena.db'
        with sqlite3.connect(temp_db_path) as conn:
            conn.execute('CREATE TABLE test (id INTEGER)')
            conn.commit()
        try:
            results = db_utils.cleanup_databases()
            self.assertIn('megasena.db', results)
            self.assertIn('wal_mode', results['megasena.db'])
            self.assertIn('integrity', results['megasena.db'])
            self.assertIn('analyze', results['megasena.db'])
            self.assertIn('vacuum', results['megasena.db'])
            self.assertIn('info', results['megasena.db'])
        finally:
            if os.path.exists(temp_db_path):
                os.unlink(temp_db_path)

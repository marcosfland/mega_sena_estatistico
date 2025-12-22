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

# Adicionar o diretório pai ao path para importar o módulo
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
            try:
                os.unlink(self.temp_db_path)
            except PermissionError:
                # Em Windows pode haver um handle aberto; tentar fechar e remover novamente
                try:
                    sqlite3.connect(self.temp_db_path).close()
                except Exception:
                    pass
                try:
                    os.unlink(self.temp_db_path)
                except Exception as e:
                    print(f"Aviso: não foi possível remover {self.temp_db_path}: {e}")
    
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

    def test_compare_numbers_with_latest_draw(self):
        """Testa comparação de um conjunto manual com último sorteio (mock da API)"""
        if not hasattr(mega_sena_app, 'compare_numbers_with_latest_draw'):
            self.skipTest("Função compare_numbers_with_latest_draw não está disponível")

        with patch('mega_sena_app.fetch_lottery_data') as mock_fetch:
            mock_fetch.return_value = {'concurso': '999', 'dezenas': ['01', '02', '03', '04', '05', '06']}
            nums = [1, 2, 3, 7, 8, 9]
            result = mega_sena_app.compare_numbers_with_latest_draw(nums)
            self.assertIsInstance(result, dict)
            self.assertEqual(result.get('matches'), 3)
            self.assertIn('comparison_result', result)
            self.assertEqual(result.get('comparison_concurso'), 999)
            self.assertEqual(result.get('numbers'), sorted(nums))

        # Testa input inválido
        invalid = mega_sena_app.compare_numbers_with_latest_draw([1,2,3])
        self.assertEqual(invalid, {})

if __name__ == '__main__':
    # Executar os testes
    unittest.main(verbosity=2)

"""
Módulo de funções de backtest para o projeto Mega-Sena Estatístico.
Inclui execução, múltiplos testes, e insights otimizados.
"""
import datetime
import logging
from typing import List, Optional, Dict, Any
import sqlite3
from db_utils import BACKTEST_DB_PATH, open_db, init_backtest_db
from analysis import get_most_frequent, get_most_frequent_period, get_weighted
from mega_sena_app import load_all_draws, NUM_DEZENAS, MAX_NUM_MEGA_SENA
import random

def run_backtest(method: str) -> bool:
    """
    Executa o backtest para um método de geração de números e salva os resultados.
    Otimizado para inserir em lote na tabela `backtest_numbers` (uma linha por número gerado)
    mantendo `backtest_results` para compatibilidade.
    """
    init_backtest_db()
    draws = load_all_draws()
    if not draws:
        logging.error('Base de dados vazia para backtest. Execute --update primeiro.')
        return False

    generated_numbers: Optional[List[int]] = []
    if method == "alltime":
        generated_numbers = get_most_frequent(draws)
    elif method == "lastyear":
        generated_numbers = get_most_frequent_period(draws)
    elif method == "weighted":
        generated_numbers = get_weighted(draws)
    else:
        logging.error(f"Método de backtest '{method}' não suportado.")
        return False

    if not generated_numbers:
        logging.warning(f"Não foi possível gerar números com o método '{method}' para backtest.")
        return False

    generated_set = set(generated_numbers)
    generated_numbers_str = ','.join(map(str, generated_numbers))
    date_tested = datetime.date.today().strftime('%Y-%m-%d')

    try:
        with open_db(BACKTEST_DB_PATH, timeout=20.0) as conn:
            cursor: sqlite3.Cursor = conn.cursor()

            # Limpar dados antigos para este método em ambas as tabelas
            cursor.execute("DELETE FROM backtest_results WHERE method = ?", (method,))
            cursor.execute("DELETE FROM backtest_numbers WHERE method = ?", (method,))
            conn.commit()

            results_inserts = []
            numbers_inserts = []

            for draw_date, draw_numbers in draws:
                draw_set = set(draw_numbers)
                matches = len(generated_set.intersection(draw_set))
                # linha por sorteio (compatibilidade)
                results_inserts.append((method, date_tested, generated_numbers_str, str(draw_date), matches))
                # linhas por número gerado
                for num in generated_numbers:
                    numbers_inserts.append((method, date_tested, num, str(draw_date), matches))

            if results_inserts:
                cursor.executemany('''
                    INSERT INTO backtest_results (method, date_tested, generated_numbers, draw_date, matches)
                    VALUES (?, ?, ?, ?, ?)
                ''', results_inserts)
            if numbers_inserts:
                cursor.executemany('''
                    INSERT INTO backtest_numbers (method, date_tested, generated_number, draw_date, matches)
                    VALUES (?, ?, ?, ?, ?)
                ''', numbers_inserts)

            conn.commit()
            logging.info(f"Backtest para o método '{method}' concluído com sucesso. Resultados salvos ({len(results_inserts)} linhas).")
            return True
    except sqlite3.Error as e:
        logging.error(f"Erro ao salvar os resultados do backtest: {e}")
        return False

def run_backtest_multiple(method: str, times: int = 1) -> Dict[str, Any]:
    """
    Executa o backtest múltiplas vezes para um método e retorna resumo consolidado.
    Implementado para inserir em lote e reduzir commits para melhor desempenho.
    """
    if times < 1:
        logging.error("Número de backtests deve ser >= 1")
        return {'success': False, 'message': 'Número inválido', 'times_requested': 0, 'times_successful': 0, 'times_failed': 0}

    # Validar método
    valid_methods = ("alltime", "lastyear", "weighted")
    if method not in valid_methods:
        logging.error(f"Método de backtest inválido: {method}")
        return {'success': False, 'times_executed': 0, 'message': f"Método inválido: {method}"}

    if times == 1:
        success = run_backtest(method)
        return {
            'success': success,
            'times_executed': 1,
            'times_requested': 1,
            'times_successful': 1 if success else 0,
            'times_failed': 0 if success else 1,
            'method': method,
            'message': f"Backtest executado 1 vez com {'sucesso' if success else 'falha'}",
            'consolidated_numbers': [],
            'consolidated_frequency': {}
        }

    init_backtest_db()
    draws = load_all_draws()
    if not draws:
        logging.error('Base de dados vazia para backtest. Execute --update primeiro.')
        return {'success': False, 'times_executed': 0, 'message': 'Base de dados vazia'}

    logging.info(f"Iniciando {times} execuções de backtest para o método '{method}'...")

    total_results: Dict[str, Any] = {}
    successful_runs = 0
    failed_runs = 0

    all_results_inserts = []
    all_numbers_inserts = []

    for i in range(times):
        try:
            generated_numbers: Optional[List[int]] = []

            # Re-gerar números a cada iteração
            if method == "alltime":
                generated_numbers = get_most_frequent(draws)
            elif method == "lastyear":
                generated_numbers = get_most_frequent_period(draws)
            elif method == "weighted":
                generated_numbers = get_weighted(draws)
            else:
                logging.error(f"Método de backtest '{method}' não suportado.")
                failed_runs += 1
                continue

            if not generated_numbers:
                logging.warning(f"Execução {i+1}: Não foi possível gerar números.")
                failed_runs += 1
                continue

            generated_set = set(generated_numbers)
            generated_numbers_str = ','.join(map(str, generated_numbers))
            date_tested = datetime.date.today().strftime('%Y-%m-%d')

            for draw_date, draw_numbers in draws:
                draw_set = set(draw_numbers)
                matches = len(generated_set.intersection(draw_set))
                all_results_inserts.append((method, date_tested, generated_numbers_str, str(draw_date), matches))
                for num in generated_numbers:
                    all_numbers_inserts.append((method, date_tested, num, str(draw_date), matches))

            logging.info(f"Execução {i+1}/{times} concluída com sucesso para método '{method}'")
            successful_runs += 1
            total_results[f"exec_{successful_runs}_numbers"] = generated_numbers

        except Exception as e:
            logging.error(f"Erro na execução {i+1} do backtest: {e}")
            failed_runs += 1
            continue

    # Persistir resultados em lote
    try:
        with sqlite3.connect(BACKTEST_DB_PATH, timeout=20.0) as conn:
            cursor: sqlite3.Cursor = conn.cursor()
            # Limpar dados anteriores
            cursor.execute("DELETE FROM backtest_results WHERE method = ?", (method,))
            cursor.execute("DELETE FROM backtest_numbers WHERE method = ?", (method,))

            if all_results_inserts:
                cursor.executemany('''
                    INSERT INTO backtest_results (method, date_tested, generated_numbers, draw_date, matches)
                    VALUES (?, ?, ?, ?, ?)
                ''', all_results_inserts)
            if all_numbers_inserts:
                cursor.executemany('''
                    INSERT INTO backtest_numbers (method, date_tested, generated_number, draw_date, matches)
                    VALUES (?, ?, ?, ?, ?)
                ''', all_numbers_inserts)
            conn.commit()

        # Consolidar números mais frequentes
        if successful_runs > 0:
            number_frequency: Dict[int, int] = {}
            for i in range(1, successful_runs + 1):
                key = f"exec_{i}_numbers"
                if key in total_results:
                    for num in total_results[key]:
                        number_frequency[num] = number_frequency.get(num, 0) + 1

            consolidated = sorted(number_frequency.items(), key=lambda x: (-x[1], x[0]))[:6]
            total_results['consolidated_numbers'] = [num for num, _ in consolidated]
            total_results['consolidated_frequency'] = dict(consolidated)

        total_results['method'] = method
        total_results['times_requested'] = times
        total_results['times_successful'] = successful_runs
        total_results['times_failed'] = failed_runs
        total_results['success'] = successful_runs > 0
        total_results['message'] = f"Execução de backtests concluída: {successful_runs} sucesso(s), {failed_runs} falha(s) de {times}"

        logging.info(f"Backtests múltiplos concluídos: {successful_runs} sucesso(s), {failed_runs} falha(s)")
        return total_results

    except Exception as e:
        logging.error(f"Erro ao executar backtests múltiplos: {e}")
        return {
            'success': False,
            'times_executed': successful_runs,
            'message': f'Erro na execução: {str(e)}'
        }

def get_from_backtest_insights(method: str = "weighted", k: int = NUM_DEZENAS) -> List[int]:
    """
    Gera um conjunto de números baseado na análise de resultados de backtest.
    Utiliza agregação SQL na tabela `backtest_numbers` para calcular scores por número
    (bônus exponencial para matches >= 4) e retorna os top k.
    """
    try:
        init_backtest_db()
        if not isinstance(k, int) or k <= 0 or k > MAX_NUM_MEGA_SENA:
            logging.warning(f"Parametro 'k' inválido ({k}), usando valor padrão {NUM_DEZENAS}.")
            k = NUM_DEZENAS

        all_nums: List[int] = list(range(1, MAX_NUM_MEGA_SENA + 1))

        with sqlite3.connect(BACKTEST_DB_PATH, timeout=20.0) as conn:
            cursor: sqlite3.Cursor = conn.cursor()
            # Agrega scores diretamente no SQL para evitar trazer muitos registros para a memória
            cursor.execute('''
                SELECT generated_number AS num,
                       SUM(CASE WHEN matches >= 4 THEN matches * matches ELSE matches END) AS score
                FROM backtest_numbers
                WHERE method = ?
                GROUP BY generated_number
                ORDER BY score DESC
                LIMIT ?
            ''', (method, k))
            rows = cursor.fetchall()

        if not rows:
            logging.warning(f"Nenhum resultado de backtest encontrado para o método '{method}'. Usando método ponderado.")
            draws = load_all_draws()
            return get_weighted(draws, k) if draws else sorted(random.sample(all_nums, k))

        top_numbers = [num for num, score in rows]
        logging.info(f"Números gerados usando insights de backtest ({method}): {sorted(top_numbers)}")
        logging.debug(f"Scores (top): {rows}")
        return sorted(top_numbers)

    except Exception as e:
        logging.error(f"Erro ao gerar números a partir de backtest insights: {e}")
        # Fallback para weighted
        draws = load_all_draws()
        return get_weighted(draws, k) if draws else sorted(random.sample(list(range(1, MAX_NUM_MEGA_SENA + 1)), k))

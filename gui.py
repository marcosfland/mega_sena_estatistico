import os
import sqlite3
import logging
import datetime
from typing import Optional, List, Dict, Any
from mega_sena_app import NUM_DEZENAS, MAX_NUM_MEGA_SENA, DB_PATH, load_all_draws, get_last_db_concurso, fetch_lottery_data
try:
    import pandas as pd
except ImportError:
    pd = None

# New DB path for user's generated numbers
USER_SETS_DB_PATH: str = os.getenv('MEGASENA_USER_SETS_DB_PATH', 'user_sets.db')

# --- Banco de Dados do Usuário ---
def init_user_sets_db(path: str = USER_SETS_DB_PATH) -> None:
    """
    Inicializa a base de dados SQLite para os conjuntos de números do usuário,
    criando a tabela 'user_sets' se não existir.
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(path)
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date_generated TEXT NOT NULL,
                dez1 INTEGER, dez2 INTEGER, dez3 INTEGER,
                dez4 INTEGER, dez5 INTEGER, dez6 INTEGER,
                comparison_result TEXT, -- To store 'win', 'lose', 'pending' etc.
                comparison_concurso INTEGER,
                UNIQUE(name) -- Ensure unique set names
            )
        ''')
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Erro ao inicializar o banco de dados de conjuntos do usuário: {e}")
    finally:
        if conn:
            conn.close()

def save_user_set(name: str, numbers: List[int], path: str = USER_SETS_DB_PATH) -> bool:
    """
    Salva um conjunto de 6 números gerados pelo usuário na base de dados.
    Atualiza um conjunto existente se o nome for o mesmo, caso contrário, insere um novo.
    """
    init_user_sets_db(path)
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(path)
        cursor: sqlite3.Cursor = conn.cursor()
        
        if len(numbers) != NUM_DEZENAS:
            logging.error(f"O conjunto de números deve conter {NUM_DEZENAS} dezenas.")
            return False

        # Sort numbers to ensure consistency in storage and comparison
        sorted_numbers = sorted(numbers)
        date_generated = datetime.date.today().strftime('%Y-%m-%d')

        # Check if a set with this name already exists
        cursor.execute("SELECT id FROM user_sets WHERE name = ?", (name,))
        existing_id = cursor.fetchone()

        if existing_id:
            # Update existing set
            cursor.execute(f'''
                UPDATE user_sets
                SET date_generated = ?, dez1 = ?, dez2 = ?, dez3 = ?, dez4 = ?, dez5 = ?, dez6 = ?,
                    comparison_result = NULL, comparison_concurso = NULL
                WHERE id = ?
            ''', (date_generated, *sorted_numbers, existing_id[0]))
            logging.info(f"Conjunto de números '{name}' atualizado.")
        else:
            # Insert new set
            cursor.execute(f'''
                INSERT INTO user_sets (name, date_generated, dez1, dez2, dez3, dez4, dez5, dez6, comparison_result, comparison_concurso)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
            ''', (name, date_generated, *sorted_numbers))
            logging.info(f"Novo conjunto de números '{name}' salvo.")
        
        conn.commit()
        return True
    except sqlite3.IntegrityError: # For UNIQUE constraint violations, if name is not unique (though we handle it above)
        logging.error(f"Erro: Um conjunto com o nome '{name}' já existe.")
        return False
    except sqlite3.Error as e:
        logging.error(f"Erro ao salvar/atualizar conjunto de números do usuário: {e}")
        return False
    finally:
        if conn:
            conn.close()

def load_user_sets(path: str = USER_SETS_DB_PATH) -> List[Dict[str, Any]]:
    """
    Carrega todos os conjuntos de números salvos pelo usuário.
    """
    init_user_sets_db(path)
    conn: Optional[sqlite3.Connection] = None
    user_sets: List[Dict[str, Any]] = []
    try:
        conn = sqlite3.connect(path)
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute('SELECT id, name, date_generated, dez1, dez2, dez3, dez4, dez5, dez6, comparison_result, comparison_concurso FROM user_sets')
        rows = cursor.fetchall()
        for row in rows:
            user_sets.append({
                'id': row[0],
                'name': row[1],
                'date_generated': row[2],
                'numbers': sorted([row[3], row[4], row[5], row[6], row[7], row[8]]), # Ensure sorted for consistency
                'comparison_result': row[9],
                'comparison_concurso': row[10]
            })
    except sqlite3.Error as e:
        logging.error(f"Erro ao carregar conjuntos de números do usuário: {e}")
    finally:
        if conn:
            conn.close()
    return user_sets

def delete_user_set(set_id: int, path: str = USER_SETS_DB_PATH) -> bool:
    """
    Deleta um conjunto de números do usuário pelo ID.
    """
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(path)
        cursor: sqlite3.Cursor = conn.cursor()
        cursor.execute("DELETE FROM user_sets WHERE id = ?", (set_id,))
        conn.commit()
        logging.info(f"Conjunto de números com ID {set_id} deletado.")
        return True
    except sqlite3.Error as e:
        logging.error(f"Erro ao deletar conjunto de números do usuário (ID: {set_id}): {e}")
        return False
    finally:
        if conn:
            conn.close()

def compare_user_sets_with_latest_draw(user_sets_path: str = USER_SETS_DB_PATH, mega_sena_db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Compara todos os conjuntos de números do usuário com o último sorteio da Mega-Sena.
    Atualiza o banco de dados do usuário com os resultados da comparação.
    Retorna uma lista de dicionários com os resultados da comparação.
    """
    latest_draw_data: Optional[Dict[str, Any]] = None
    try:
        # Fetch the latest Mega-Sena draw from the official DB or API
        # It's safer to get from API directly for latest, then from DB for historical
        # Let's assume the official DB is updated by --update, so we check latest from there.
        all_draws = load_all_draws(mega_sena_db_path)
        if not all_draws:
            logging.warning("Base de dados da Mega-Sena vazia. Não é possível comparar os conjuntos.")
            return []
        
        # The `load_all_draws` sorts by concurso, so the last one is the latest.
        # However, for the *absolute latest* to compare with, fetching from API is more robust for a direct check.
        # But for consistency, let's use the DB's latest entry.
        latest_concurso_db = get_last_db_concurso(mega_sena_db_path)
        
        # Find the actual draw for the latest_concurso_db
        latest_draw_tuple = None
        for d, nums in all_draws:
            # We need the concurso number, which load_all_draws doesn't return directly.
            # Let's modify load_all_draws to include concurso, or fetch specifically.
            # For simplicity, let's fetch from API if we need the absolute latest,
            # or rely on load_all_draws and find the latest based on date/concurso in memory.
            # For this scenario, let's adapt `fetch_lottery_data` to get the latest.
            try:
                latest_draw_api = fetch_lottery_data("megasena", None) # Get latest from API
                latest_draw_number = int(latest_draw_api['concurso'])
                latest_draw_dezenas = sorted(list(map(int, latest_draw_api['dezenas'])))
                latest_draw_data = {
                    'concurso': latest_draw_number,
                    'dezenas': latest_draw_dezenas
                }
                break # Found the latest from API
            except Exception as e:
                logging.warning(f"Não foi possível buscar o último sorteio da API para comparação: {e}. Tentando usar o último do DB.")
                if all_draws:
                    # Sort draws by date and then by concurso (if concurso was available)
                    # For current `load_all_draws` that doesn't return concurso, we'll just take the last date's entry.
                    # Or better, read concurso from DB in load_all_draws.
                    # Let's adjust `load_all_draws` to also return `concurso`.
                    
                    # TEMPORARY FIX: Fetch latest concurso from DB, then fetch that specific draw from API
                    # This avoids modifying `load_all_draws` for now, but `fetch_lottery_data` is best.
                    
                    # Re-calling `fetch_lottery_data` for the latest (API) is the most direct.
                    # If API fails, then fall back to loading from local DB and finding max_concurso from there.
                    conn_db = sqlite3.connect(mega_sena_db_path)
                    cursor_db = conn_db.cursor()
                    cursor_db.execute('SELECT concurso, data, dez1, dez2, dez3, dez4, dez5, dez6 FROM megasena ORDER BY concurso DESC LIMIT 1')
                    last_db_row = cursor_db.fetchone()
                    conn_db.close()

                    if last_db_row:
                        latest_draw_data = {
                            'concurso': last_db_row[0],
                            'dezenas': sorted([last_db_row[i] for i in range(2, 8)]) # dezenas are from index 2 to 7
                        }
                    else:
                        logging.error("Nenhum sorteio encontrado no banco de dados local da Mega-Sena.")
                        return []
                else:
                    logging.error("Base de dados da Mega-Sena vazia e API indisponível.")
                    return []


    except Exception as e:
        logging.error(f"Erro ao obter o último sorteio da Mega-Sena para comparação: {e}")
        return []

    if latest_draw_data is None:
        return [] # Should not happen if previous blocks handle errors

    latest_concurso_num = latest_draw_data['concurso']
    latest_dezenas = set(latest_draw_data['dezenas'])

    user_sets = load_user_sets(user_sets_path)
    comparison_results = []
    
    conn_user = None
    try:
        conn_user = sqlite3.connect(user_sets_path)
        cursor_user = conn_user.cursor()

        for user_set in user_sets:
            user_set_numbers = set(user_set['numbers'])
            matches = len(user_set_numbers.intersection(latest_dezenas))
            
            result_text = "Perdeu"
            # Mega-Sena prizes: Sena (6), Quina (5), Quadra (4)
            if matches == 6:
                result_text = "Sena (6 acertos)!"
            elif matches == 5:
                result_text = "Quina (5 acertos)!"
            elif matches == 4:
                result_text = "Quadra (4 acertos)!"
            elif matches == 3: # Often 3 matches also get a small prize (terno)
                result_text = "Terno (3 acertos)"
            else:
                result_text = f"Nenhum prêmio ({matches} acertos)"

            # Update the user_sets DB with comparison result and concurso
            cursor_user.execute(f'''
                UPDATE user_sets
                SET comparison_result = ?, comparison_concurso = ?
                WHERE id = ?
            ''', (result_text, latest_concurso_num, user_set['id']))
            
            user_set['comparison_result'] = result_text
            user_set['comparison_concurso'] = latest_concurso_num
            user_set['matches'] = matches # Add matches count for display
            user_set['latest_draw_dezenas'] = sorted(list(latest_dezenas)) # Add for display
            
            comparison_results.append(user_set)
        
        conn_user.commit()

    except sqlite3.Error as e:
        logging.error(f"Erro ao atualizar resultados de comparação na base de dados de conjuntos do usuário: {e}")
    finally:
        if conn_user:
            conn_user.close()
    
    return comparison_results

def calculate_correlation(draws):
    """
    Calcula a matriz de correlação entre os números sorteados.
    """
    if pd is None:
        logging.error("Pandas não está instalado. Não é possível calcular a correlação.")
        return None

    data = []
    for _, nums in draws:
        draw_binary = [1 if i in nums else 0 for i in range(1, MAX_NUM_MEGA_SENA + 1)]
        data.append(draw_binary)

    if not data:
        logging.warning("Não há dados de sorteios para calcular a correlação.")
        return None

    df = pd.DataFrame(data, columns=[f'Num_{i}' for i in range(1, MAX_NUM_MEGA_SENA + 1)])
    correlation_matrix = df.corr()
    return correlation_matrix

def main():
    import tkinter as tk
    from tkinter import messagebox, simpledialog
    root = tk.Tk()
    root.geometry("500x400")
    root.title("Mega-Sena - Gerenciador de Conjuntos do Usuário")
    tk.Label(root, text="Mega-Sena - Gerenciador de Conjuntos do Usuário", font=("Arial", 14, "bold")).pack(pady=10)
    
    # Botões principais
    tk.Button(root, text="Salvar conjunto por frequência", width=30, command=lambda: messagebox.showinfo("Info", "Funcionalidade de salvar por frequência")).pack(pady=5)
    tk.Button(root, text="Salvar conjunto ponderado", width=30, command=lambda: messagebox.showinfo("Info", "Funcionalidade de salvar ponderado")).pack(pady=5)
    tk.Button(root, text="Comparar conjuntos salvos com último sorteio", width=30, command=lambda: messagebox.showinfo("Info", "Funcionalidade de comparação")).pack(pady=5)
    tk.Button(root, text="Listar conjuntos salvos", width=30, command=lambda: messagebox.showinfo("Info", "Funcionalidade de listagem")).pack(pady=5)
    tk.Button(root, text="Deletar conjunto salvo", width=30, command=lambda: messagebox.showinfo("Info", "Funcionalidade de deletar conjunto")).pack(pady=5)
    tk.Button(root, text="Sair", width=30, command=root.quit).pack(pady=20)
    root.mainloop()

if __name__ == "__main__":
    main()
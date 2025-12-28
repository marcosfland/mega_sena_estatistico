"""
Módulo principal da interface gráfica do Mega-Sena Estatístico.
Contém a lógica da GUI migrada de gui.py.
"""


import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
from gui_utils import show_message, ask_on_main_thread
from mega_sena_app import load_all_draws, NUM_DEZENAS

# Variáveis globais da GUI
root = None
status_bar = None
progress_bar = None
interactive_buttons = []

def main():
    global root, status_bar, progress_bar, interactive_buttons
    root = tk.Tk()
    root.title("Mega-Sena Estatístico")
    root.geometry("700x950")

    # Status bar
    status_bar = ttk.Label(root, text="Pronto", anchor="w")
    status_bar.pack(side="bottom", fill="x")

    # Progress bar
    progress_bar = ttk.Progressbar(root, mode="indeterminate")
    progress_bar.pack(side="bottom", fill="x")

    # Botões principais
    frame = ttk.Frame(root)
    frame.pack(pady=20)

    btn_alltime = ttk.Button(frame, text="Top 6 de Todos os Tempos", command=lambda: run_analysis_gui('alltime'))
    btn_lastyear = ttk.Button(frame, text="Top 6 do Último Ano", command=lambda: run_analysis_gui('lastyear'))
    btn_stat = ttk.Button(frame, text="Conjunto Estatístico Ponderado", command=lambda: run_analysis_gui('stat'))
    btn_prediction = ttk.Button(frame, text="Predição Inteligente", command=lambda: run_analysis_gui('prediction'))
    btn_gaps = ttk.Button(frame, text="Análise de Intervalos", command=lambda: run_analysis_gui('gaps'))
    btn_cycles = ttk.Button(frame, text="Padrões Cíclicos", command=lambda: run_analysis_gui('cycles'))
    btn_sequences = ttk.Button(frame, text="Análise de Sequências", command=lambda: run_analysis_gui('sequences'))

    btn_alltime.grid(row=0, column=0, padx=10, pady=5)
    btn_lastyear.grid(row=0, column=1, padx=10, pady=5)
    btn_stat.grid(row=0, column=2, padx=10, pady=5)
    btn_prediction.grid(row=1, column=0, padx=10, pady=5)
    btn_gaps.grid(row=1, column=1, padx=10, pady=5)
    btn_cycles.grid(row=1, column=2, padx=10, pady=5)
    btn_sequences.grid(row=2, column=1, padx=10, pady=5)

    interactive_buttons = [btn_alltime, btn_lastyear, btn_stat, btn_prediction, btn_gaps, btn_cycles, btn_sequences]

    # Resultados
    result_text = tk.Text(root, height=30, width=90, state="disabled")
    result_text.pack(pady=10)

    def set_result(text):
        result_text.config(state="normal")
        result_text.delete(1.0, tk.END)
        result_text.insert(tk.END, text)
        result_text.config(state="disabled")

    def run_analysis_gui(tipo):
        def worker():
            try:
                progress_bar.start()
                status_bar.config(text="Processando...")
                for btn in interactive_buttons:
                    btn.config(state="disabled")
                root.config(cursor="watch")
                draws = load_all_draws()
                if not draws:
                    show_message("Erro", "Base de dados vazia. Execute a atualização primeiro.", is_error=True)
                    return
                if tipo == 'alltime':
                    from analysis import get_most_frequent
                    result = get_most_frequent(draws)
                    set_result(f"Top 6 de todos os tempos: {result}")
                elif tipo == 'lastyear':
                    from analysis import get_most_frequent_period
                    result = get_most_frequent_period(draws)
                    set_result(f"Top 6 do último ano: {result}")
                elif tipo == 'stat':
                    from analysis import get_weighted
                    result = get_weighted(draws)
                    set_result(f"Conjunto estatístico ponderado: {result}")
                elif tipo == 'prediction':
                    from mega_sena_app import generate_smart_prediction
                    prediction = generate_smart_prediction(draws)
                    top_6 = [num for num, _ in prediction[:6]]
                    set_result(f"Predição Inteligente (Top 6): {top_6}\n\nScores: {prediction}")
                elif tipo == 'gaps':
                    from mega_sena_app import analyze_number_gaps
                    gaps = analyze_number_gaps(draws)
                    avg_gaps = {num: sum(gap_list)/len(gap_list) if gap_list else 0 for num, gap_list in gaps.items()}
                    sorted_gaps = sorted(avg_gaps.items(), key=lambda x: x[1], reverse=True)
                    text = "Intervalos médios (Top 10):\n" + "\n".join([f"{num}: {gap:.1f}" for num, gap in sorted_gaps[:10]])
                    set_result(text)
                elif tipo == 'cycles':
                    from mega_sena_app import analyze_cycles
                    cycles = analyze_cycles(draws)
                    text = "Distribuição por dia da semana:\n" + str(cycles['weekday_distribution'])
                    text += "\nDistribuição por mês:\n" + str(cycles['month_distribution'])
                    set_result(text)
                elif tipo == 'sequences':
                    from mega_sena_app import analyze_sequences
                    sequences = analyze_sequences(draws)
                    text = "Distribuição de números consecutivos:\n" + str(sequences['consecutive_distribution'])
                    text += "\nProgressões aritméticas mais comuns:\n" + str(sequences['arithmetic_progressions'])
                    set_result(text)
                else:
                    set_result("Seleção inválida.")
            except Exception as e:
                logging.exception(e)
                show_message("Erro", str(e), is_error=True)
            finally:
                progress_bar.stop()
                status_bar.config(text="Pronto")
                for btn in interactive_buttons:
                    btn.config(state="normal")
                root.config(cursor="")
        threading.Thread(target=worker, daemon=True).start()

    # Expor função para testes
    globals()['run_analysis_gui'] = run_analysis_gui

    root.mainloop()

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
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TButton", font=("Segoe UI", 11), padding=8, relief="flat")
    style.configure("TLabel", font=("Segoe UI", 10))
    root.configure(bg="#f7f7fa")

    # Status bar

    status_bar = ttk.Label(root, text="✅ Pronto", anchor="w", background="#e9ecef")
    status_bar.pack(side="bottom", fill="x", padx=0, pady=0)

    # Progress bar

    progress_bar = ttk.Progressbar(root, mode="indeterminate")
    progress_bar.pack(side="bottom", fill="x", padx=0, pady=0)

    # Botões principais

    frame = ttk.Frame(root, padding=10)
    frame.pack(pady=20)


    from gui_utils import Tooltip

    btn_alltime = ttk.Button(frame, text="Top 6 de Todos os Tempos", command=lambda: run_analysis_gui('alltime'))
    btn_lastyear = ttk.Button(frame, text="Top 6 do Último Ano", command=lambda: run_analysis_gui('lastyear'))
    btn_stat = ttk.Button(frame, text="Conjunto Estatístico Ponderado", command=lambda: run_analysis_gui('stat'))
    btn_prediction = ttk.Button(frame, text="Predição Inteligente", command=lambda: run_analysis_gui('prediction'))
    btn_gaps = ttk.Button(frame, text="Análise de Intervalos", command=lambda: run_analysis_gui('gaps'))
    btn_cycles = ttk.Button(frame, text="Padrões Cíclicos", command=lambda: run_analysis_gui('cycles'))
    btn_sequences = ttk.Button(frame, text="Análise de Sequências", command=lambda: run_analysis_gui('sequences'))
    btn_graph = ttk.Button(frame, text="Visualizar Gráfico", command=lambda: open_graph_window())

    Tooltip(btn_alltime, "Números mais sorteados em toda a história")
    Tooltip(btn_lastyear, "Números mais sorteados no último ano")
    Tooltip(btn_stat, "Conjunto ponderado pela frequência histórica")
    Tooltip(btn_prediction, "Predição baseada em score inteligente")
    Tooltip(btn_gaps, "Intervalos médios entre aparições")
    Tooltip(btn_cycles, "Distribuição por dia/mês")
    Tooltip(btn_sequences, "Sequências e progressões numéricas")


    btn_alltime.grid(row=0, column=0, padx=10, pady=5)
    btn_lastyear.grid(row=0, column=1, padx=10, pady=5)
    btn_stat.grid(row=0, column=2, padx=10, pady=5)
    btn_prediction.grid(row=1, column=0, padx=10, pady=5)
    btn_gaps.grid(row=1, column=1, padx=10, pady=5)
    btn_cycles.grid(row=1, column=2, padx=10, pady=5)
    btn_sequences.grid(row=2, column=1, padx=10, pady=5)
    btn_graph.grid(row=2, column=2, padx=10, pady=5)

    interactive_buttons = [btn_alltime, btn_lastyear, btn_stat, btn_prediction, btn_gaps, btn_cycles, btn_sequences, btn_graph]
    def open_graph_window():
        import matplotlib
        matplotlib.use('TkAgg')
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        import datetime

        graph_win = tk.Toplevel(root)
        graph_win.title("Gráficos Interativos - Mega-Sena Estatístico")
        graph_win.geometry("800x600")

        # Filtros
        filter_frame = ttk.Frame(graph_win)
        filter_frame.pack(side="top", fill="x", padx=10, pady=5)
        ttk.Label(filter_frame, text="Período (dias):").pack(side="left")
        period_var = tk.IntVar(value=365)
        period_entry = ttk.Entry(filter_frame, textvariable=period_var, width=6)
        period_entry.pack(side="left", padx=5)
        ttk.Label(filter_frame, text="Quantidade de números:").pack(side="left", padx=10)
        k_var = tk.IntVar(value=6)
        k_entry = ttk.Entry(filter_frame, textvariable=k_var, width=4)
        k_entry.pack(side="left", padx=5)

        fig, ax = plt.subplots(figsize=(8, 4))
        canvas = FigureCanvasTkAgg(fig, master=graph_win)
        canvas.get_tk_widget().pack(fill="both", expand=True)

        def plot_graph():
            ax.clear()
            draws = load_all_draws()
            if not draws:
                ax.text(0.5, 0.5, "Base de dados vazia", ha="center", va="center", fontsize=14)
                canvas.draw()
                return
            # Filtrar por período
            days = period_var.get()
            today = datetime.date.today()
            cutoff = today - datetime.timedelta(days=days)
            filtered = [(d, nums) for d, nums in draws if d >= cutoff]
            from analysis import get_most_frequent
            freq = get_most_frequent(filtered, k=k_var.get())
            # Histograma de frequência
            all_nums = [num for _, nums in filtered for num in nums]
            ax.hist(all_nums, bins=range(1, 62), color="#4e79a7", edgecolor="white")
            ax.set_title(f"Frequência dos Números - Últimos {days} dias")
            ax.set_xlabel("Número")
            ax.set_ylabel("Ocorrências")
            ax.grid(True, linestyle="--", alpha=0.5)
            # Destacar os mais frequentes
            for n in freq:
                ax.axvline(n, color="#e15759", linestyle="--", alpha=0.7)
            canvas.draw()

        ttk.Button(filter_frame, text="Atualizar Gráfico", command=plot_graph).pack(side="left", padx=10)
        plot_graph()

    # Resultados

    result_text = tk.Text(root, height=30, width=90, state="disabled", font=("Consolas", 11), bg="#f7f7fa", relief="flat", borderwidth=2)
    result_text.pack(pady=10)


    def set_result(text, success=True):
        result_text.config(state="normal")
        result_text.delete(1.0, tk.END)
        result_text.insert(tk.END, text)
        result_text.config(state="disabled")
        if success:
            status_bar.config(text="✅ Operação concluída com sucesso")
        else:
            status_bar.config(text="❌ Ocorreu um erro")

    def run_analysis_gui(tipo):
        def worker():
            try:
                progress_bar.start()
                status_bar.config(text="⏳ Processando...")
                for btn in interactive_buttons:
                    btn.config(state="disabled")
                root.config(cursor="watch")
                draws = load_all_draws()
                if not draws:
                    show_message("Erro", "Base de dados vazia. Execute a atualização primeiro.", is_error=True)
                    set_result("Base de dados vazia. Execute a atualização primeiro.", success=False)
                    return
                if tipo == 'alltime':
                    from analysis import get_most_frequent
                    result = get_most_frequent(draws)
                    set_result(f"Top 6 de todos os tempos:\n  {', '.join(str(n) for n in result)}")
                elif tipo == 'lastyear':
                    from analysis import get_most_frequent_period
                    result = get_most_frequent_period(draws)
                    set_result(f"Top 6 do último ano:\n  {', '.join(str(n) for n in result)}")
                elif tipo == 'stat':
                    from analysis import get_weighted
                    result = get_weighted(draws)
                    set_result(f"Conjunto estatístico ponderado:\n  {', '.join(str(n) for n in result)}")
                elif tipo == 'prediction':
                    from mega_sena_app import generate_smart_prediction
                    prediction = generate_smart_prediction(draws)
                    top_6 = [num for num, _ in prediction[:6]]
                    scores_str = '\n'.join([f"{num}: {score:.3f}" for num, score in prediction[:10]])
                    set_result(f"Predição Inteligente (Top 6):\n  {', '.join(str(n) for n in top_6)}\n\nScores (Top 10):\n{scores_str}")
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
                    text = "Distribuição por dia da semana:\n" + '\n'.join([f"{k}: {v}" for k, v in cycles['weekday_distribution'].items()])
                    text += "\nDistribuição por mês:\n" + '\n'.join([f"{k}: {v}" for k, v in cycles['month_distribution'].items()])
                    set_result(text)
                elif tipo == 'sequences':
                    from mega_sena_app import analyze_sequences
                    sequences = analyze_sequences(draws)
                    text = "Distribuição de números consecutivos:\n" + '\n'.join([f"{k}: {v}" for k, v in sequences['consecutive_distribution'].items()])
                    text += "\nProgressões aritméticas mais comuns:\n" + '\n'.join([str(p) for p in sequences['arithmetic_progressions'][:10]])
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

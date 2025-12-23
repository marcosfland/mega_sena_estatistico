import tkinter as tk
from tkinter import messagebox, filedialog, Menu, simpledialog, ttk
from mega_sena_app import (
    load_all_draws, get_most_frequent, get_most_frequent_period,
    get_weighted, monte_carlo_simulation, plot_frequency,
    calculate_correlation, analyze_time_series, analyze_probability_distribution,
    update_db, export_results, get_most_frequent_pairs, get_most_frequent_triplets,
    conditional_probability, filter_draws_by_period, sanitize_filename,
    save_user_set, load_user_sets, compare_user_sets_with_latest_draw, compare_numbers_with_latest_draw,
    run_backtest, get_backtest_summary, generate_smart_prediction, get_from_backtest_insights,
    analyze_number_gaps, analyze_cycles, analyze_sequences,
    find_exact_sequence, find_best_match_draw,
    NUM_DEZENAS, MAX_NUM_MEGA_SENA
)
import webbrowser
from collections import Counter
import os
import datetime
import logging
import subprocess
import threading
import sys
from typing import Optional, List, Dict, Any
from config import get_config, get_db_path
from gui_db import select_db_gui
# Matplotlib embedding (opcional)
try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except Exception:
    FigureCanvasTkAgg = None
try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None
    ImageDraw = None
    logging.warning("Pillow não está instalado. O ícone da aplicação pode não ser exibido.")

logging.basicConfig(filename="gui_actions.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

root = None
status_bar = None
compare_button = None
compare_hint_label = None
progress_bar = None
interactive_buttons = []  # Lista de botões que devem ser desativados durante processamento

def show_message(title, message, is_error=False):
    """Mostra mensagens de forma thread-safe (agendando no mainloop quando necessário)."""
    try:
        is_main = threading.current_thread() is threading.main_thread()
    except Exception:
        is_main = True

    def _show():
        if status_bar:
            status_bar.config(text=message)
        if is_error:
            logging.error(f"{title}: {message}")
            messagebox.showerror(title, message)
        else:
            logging.info(f"{title}: {message}")
            messagebox.showinfo(title, message)
        if root and status_bar:
            root.after(5000, lambda: status_bar.config(text="Pronto") if status_bar else None)

    if is_main or root is None:
        _show()
    else:
        root.after(0, _show)


def ask_on_main_thread(func, *args, **kwargs):
    """Executa uma chamada de UI no thread principal de forma síncrona e retorna o resultado.

    Usa um Event para aguardar o término da chamada agendada via root.after. Se já estiver
    no thread principal, executa diretamente.
    """
    try:
        if threading.current_thread() is threading.main_thread() or root is None:
            return func(*args, **kwargs)
    except Exception:
        # Se qualquer verificação falhar, tente executar diretamente
        return func(*args, **kwargs)

    result = {}
    evt = threading.Event()

    def _call():
        try:
            result['value'] = func(*args, **kwargs)
        except Exception as e:
            result['exc'] = e
        finally:
            evt.set()

    # Agendar no loop principal
    root.after(0, _call)
    # Aguardar retorno
    evt.wait()
    if 'exc' in result:
        # Re-levantar a exceção no thread chamador para que ela seja tratada
        raise result['exc']
    return result.get('value')


class Tooltip:
    """Simples tooltip para widgets Tkinter."""
    def __init__(self, widget, text=""):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)

    def _on_enter(self, event=None):
        self.showtip()

    def _on_leave(self, event=None):
        self.hidetip()

    def showtip(self):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT, background="#ffffe0", relief=tk.SOLID, borderwidth=1, font=("tahoma", "8", "normal"))
        label.pack(ipadx=4, ipady=2)

    def hidetip(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

    def set_text(self, text):
        self.text = text

def open_file_location(filepath):
    try:
        folder = os.path.dirname(os.path.abspath(filepath))
        if os.name == 'nt':
            os.startfile(folder)
        elif os.name == 'posix':
            subprocess.Popen(['xdg-open', folder])
        show_message("Local Aberto", f"A pasta de '{filepath}' foi aberta.", False)
    except Exception as e:
        show_message("Erro", f"Não foi possível abrir o local do arquivo: {e}", True)

def run_in_thread(func, *args, **kwargs):
    if status_bar:
        status_bar.config(text="Processando... Por favor, aguarde.")
    thread = threading.Thread(target=lambda: func(*args, **kwargs))
    thread.start()

def start_processing():
    """Ativa indicadores visuais de processamento: barra de progresso, cursor e desabilita botões."""
    try:
        if status_bar:
            status_bar.config(text="Processando... Por favor, aguarde.")
        if progress_bar:
            progress_bar.start(10)
        if root:
            try:
                root.config(cursor='watch')
            except Exception:
                root.config(cursor='')
        for b in interactive_buttons:
            try:
                b.config(state=tk.DISABLED)
            except Exception:
                pass
    except Exception as e:
        logging.warning(f"Erro ao iniciar indicador de processamento: {e}")


def display_results_table(headers, rows):
    """Preenche o Treeview com os cabeçalhos e linhas fornecidas.

    headers: lista de strings para as colunas
    rows: lista de iterables que correspondem às colunas
    """
    global results_tree, current_results_data, current_results_headers
    try:
        if not results_tree:
            return
        # limpar árvore
        for col in results_tree['columns']:
            results_tree.heading(col, text='')
        results_tree.delete(*results_tree.get_children())

        # definir novas colunas
        results_tree['columns'] = headers
        for h in headers:
            results_tree.heading(h, text=h)
            results_tree.column(h, width=100, anchor=tk.W)

        # inserir linhas
        for r in rows:
            results_tree.insert('', tk.END, values=list(r))

        current_results_headers = headers
        current_results_data = [list(r) for r in rows]
    except Exception as e:
        logging.error(f"Erro ao exibir resultados na Treeview: {e}")


def export_results_gui():
    """Exporta os resultados atualmente exibidos na Treeview para arquivo CSV/JSON."""
    global current_results_headers, current_results_data
    try:
        if not current_results_data or not current_results_headers:
            show_message("Erro", "Nenhum resultado disponível para exportar.", True)
            return

        file_path = ask_on_main_thread(filedialog.asksaveasfilename, defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json")], parent=root)
        if not file_path:
            return

        file_format = file_path.split('.')[-1]
        filename_base = sanitize_filename(os.path.splitext(os.path.basename(file_path))[0])

        # Converter para lista de tuplas
        rows = [tuple(r) for r in current_results_data]
        export_results(rows, file_format, filename_base, header=current_results_headers)
        show_message("Exportação", f"Resultados exportados para {file_path}", False)
    except Exception as e:
        show_message("Erro na Exportação", f"Falha ao exportar resultados: {e}", True)


def embed_figure(fig):
    """Insere um objeto matplotlib.figure.Figure no painel de resultados (se suportado)."""
    global mpl_canvas, results_tree
    try:
        if not FigureCanvasTkAgg:
            show_message("Gráfico", "Matplotlib/TkAgg não disponível; abrindo em janela externa.", False)
            try:
                import matplotlib.pyplot as _plt
                _plt.figure(fig.number if hasattr(fig, 'number') else None)
                _plt.show()
            except Exception:
                pass
            return

        # Remover canvas anterior
        try:
            if mpl_canvas:
                mpl_canvas.get_tk_widget().destroy()
        except Exception:
            pass

        canvas = FigureCanvasTkAgg(fig, master=results_tree.master)
        canvas.draw()
        widget = canvas.get_tk_widget()
        widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        mpl_canvas = canvas
    except Exception as e:
        logging.error(f"Erro ao embutir figura: {e}")
        show_message("Erro", f"Não foi possível embutir o gráfico: {e}", True)

def stop_processing():
    """Desativa indicadores visuais de processamento e restaura estado da UI."""
    try:
        if progress_bar:
            progress_bar.stop()
        if status_bar:
            status_bar.config(text="Pronto")
        if root:
            try:
                root.config(cursor='')
            except Exception:
                pass
        for b in interactive_buttons:
            try:
                b.config(state=tk.NORMAL)
            except Exception:
                pass
        toggle_compare_button_state()
    except Exception as e:
        logging.warning(f"Erro ao parar indicador de processamento: {e}")


def run_analysis_gui(option):
    # Iniciar indicador antes de disparar a thread
    if root:
        root.after(0, start_processing)

    def _run():
        try:
            draws = load_all_draws()
            if not draws:
                show_message("Erro", "Base de dados vazia. Execute a atualização primeiro.", True)
                return

            result_message = ""
            plot_needed = False
            
            if option == "alltime":
                result = get_most_frequent(draws)
                result_message = f"Top {NUM_DEZENAS} de Todos os Tempos: {result}"
            elif option == "lastyear":
                result = get_most_frequent_period(draws)
                if not result:
                    result_message = f"Nenhum sorteio encontrado no último ano para análise."
                else:
                    result_message = f"Top {NUM_DEZENAS} do Último Ano: {result}"
            elif option == "weighted":
                result = get_weighted(draws)
                result_message = f"Conjunto Estatístico Ponderado: {result}"
            elif option == "plot":
                plot_needed = True
            elif option == "montecarlo":
                simulated, real = monte_carlo_simulation(draws)
                result_message = f"Simulação de Monte Carlo - Números Mais Frequentes:\nSimulados (Número, Frequência): {simulated}\nReais (Número, Frequência): {real}"
            elif option == "correlation":
                correlation_matrix = calculate_correlation(draws)
                if correlation_matrix is not None:
                    show_message("Correlação", "Matriz de Correlação calculada. Para visualização completa, use a 'Exportação Avançada'.", False)
                else:
                    show_message("Erro", "Não foi possível calcular a correlação. Verifique se Pandas está instalado.", True)
                return
            elif option == "timeseries":
                plot_needed = True
            elif option == "distribution":
                result_data = analyze_probability_distribution(draws)
                if result_data is not None:
                    chi2, p = result_data
                    result_message = f"Teste Qui-quadrado:\nChi2: {chi2:.4f}, p-valor: {p:.4f}\n"
                    if p < 0.05:
                        result_message += "A distribuição observada é significativamente diferente de uma distribuição uniforme."
                    else:
                        result_message += "A distribuição observada não é significativamente diferente de uma distribuição uniforme."
                else:
                    show_message("Erro", "Não foi possível calcular a distribuição de probabilidade. Verifique se SciPy está instalado.", True)
                    return
            elif option == "pairs":
                result = get_most_frequent_pairs(draws, 10)
                # Exibir em tabela
                rows = [ (f"{a},{b}", freq) for (a, b), freq in result ]
                if root:
                    root.after(0, lambda: display_results_table(["Par", "Frequência"], rows))
                else:
                    result_message = "Pares Mais Frequentes: " + str(rows)
            elif option == "triplets":
                result = get_most_frequent_triplets(draws, 10)
                rows = [ ("-".join(map(str, triplet)), freq) for triplet, freq in result ]
                if root:
                    root.after(0, lambda: display_results_table(["Trio", "Frequência"], rows))
                else:
                    result_message = "Trios Mais Frequentes: " + str(rows)
            elif option == "conditional":
                given = simpledialog.askinteger("Probabilidade Condicional", "Informe o número dado (GIVEN):", parent=root, minvalue=1, maxvalue=MAX_NUM_MEGA_SENA)
                if given is None: return
                target = simpledialog.askinteger("Probabilidade Condicional", "Informe o número alvo (TARGET):", parent=root, minvalue=1, maxvalue=MAX_NUM_MEGA_SENA)
                if target is None: return

                if not (1 <= given <= MAX_NUM_MEGA_SENA) or not (1 <= target <= MAX_NUM_MEGA_SENA):
                    show_message("Erro", f"Números devem estar entre 1 e {MAX_NUM_MEGA_SENA}.", True)
                    return
                
                prob = conditional_probability(draws, given, target)
                result_message = f"P({target}|{given}) = {prob:.4f}"
            elif option == "period":
                start = simpledialog.askstring("Filtro por Período", "Data inicial (AAAA-MM-DD):", parent=root)
                if not start: return
                end = simpledialog.askstring("Filtro por Período", "Data final (AAAA-MM-DD):", parent=root)
                if not end: return

                try:
                    start_date = datetime.datetime.strptime(start, "%Y-%m-%d").date()
                    end_date = datetime.datetime.strptime(end, "%Y-%m-%d").date()
                    if start_date > end_date:
                        show_message("Erro", "Data de início não pode ser posterior à data de fim.", True)
                        return
                    filtered_draws = filter_draws_by_period(draws, start_date, end_date)
                    if not filtered_draws:
                        result_message = "Nenhum sorteio encontrado no período informado."
                    else:
                        result = get_most_frequent(filtered_draws)
                        result_message = f"Top {NUM_DEZENAS} no Período ({start} a {end}): {result}"
                except ValueError as e:
                    show_message("Erro", f"Formato de data inválido. Use AAAA-MM-DD. Erro: {e}", True)
                    return
            elif option == "prediction":
                prediction = generate_smart_prediction(draws)
                top_numbers = [(num, score) for num, score in prediction[:10]]
                formatted_prediction = "\n".join([f"{i}. Número {num}: Score {score:.4f}" 
                                                for i, (num, score) in enumerate(top_numbers, 1)])
                top_6 = [num for num, _ in prediction[:6]]
                result_message = f"Predição Inteligente (Top 10):\n{formatted_prediction}\n\nTop 6 Sugeridos: {top_6}"
            elif option == "backtest-insights":
                method = ask_on_main_thread(simpledialog.askstring, "Backtest Insights", "Escolha o método (alltime, lastyear, weighted):", parent=root)
                if not method:
                    return
                result = get_from_backtest_insights(method=method)
                # Exibir como tabela (índice, número)
                rows = [(i+1, n) for i, n in enumerate(result)]
                if root:
                    root.after(0, lambda: display_results_table(["Posição", "Número"], rows))
                else:
                    result_message = f"Números por Backtest Insights ({method}): {result}"
            elif option == "gaps":
                gaps = analyze_number_gaps(draws)
                avg_gaps = {num: sum(gap_list)/len(gap_list) if gap_list else 0 
                           for num, gap_list in gaps.items()}
                sorted_gaps = sorted(avg_gaps.items(), key=lambda x: x[1], reverse=True)[:10]
                rows = [ (i, num, f"{avg:.1f}") for i, (num, avg) in enumerate(sorted_gaps, 1) ]
                if root:
                    root.after(0, lambda: display_results_table(["Rank", "Número", "Gap Médio"], rows))
                else:
                    result_message = "Análise de Intervalos: " + str(rows)
            elif option == "cycles":
                cycles = analyze_cycles(draws)
                weekdays = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
                months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
                
                weekday_rows = [(weekdays[day], freq) for day, freq in cycles['weekday_distribution'].items()]
                month_rows = [(months[month-1], freq) for month, freq in cycles['month_distribution'].items()]
                # Mostrar primeiro os weekdays; o usuário pode exportar e visualizar ambos
                if root:
                    root.after(0, lambda: display_results_table(["Período", "Frequência"], weekday_rows))
                else:
                    result_message = f"Padrões Cíclicos (weekday): {weekday_rows} \n (month): {month_rows}"
            elif option == "sequences":
                sequences = analyze_sequences(draws)
                consec_info = "\n".join([f"  {consec} consecutivos: {freq}" 
                                       for consec, freq in sorted(sequences['consecutive_distribution'].items())])
                prog_info = "\n".join([f"  Diferença {diff}: {freq}" 
                                     for diff, freq in sorted(sequences['arithmetic_progressions'].items(), 
                                                            key=lambda x: x[1], reverse=True)[:5]])
                result_message = f"Análise de Sequências:\n\nNúmeros consecutivos:\n{consec_info}\n\nProgressões aritméticas:\n{prog_info}"
            
            if plot_needed:
                if option == "plot":
                    try:
                        fig = plot_frequency(draws, return_fig=True)
                        if fig and FigureCanvasTkAgg:
                            # Embutir no frame de resultados
                            if root:
                                root.after(0, lambda: embed_figure(fig))
                        else:
                            # Fallback: abrir em nova janela
                            plot_frequency(draws, return_fig=False)
                    except Exception as e:
                        logging.error(f"Erro ao gerar gráfico embutido: {e}")
                elif option == "timeseries":
                    # timeseries ainda exibe usando a implementação existente
                    analyze_time_series(draws)
                show_message("Gráfico Exibido", "Verifique a janela do gráfico ou o painel de Resultados.", False)
            else:
                show_message("Análise Concluída", result_message, False)

        except Exception as e:
            show_message("Erro na Análise", f"Ocorreu um erro ao executar a análise '{option}': {e}", True)
        finally:
            # Sempre parar o indicador ao final
            if root:
                root.after(0, stop_processing)
    
    run_in_thread(_run)

def export_data_gui(advanced=False):
    def _export():
        try:
            draws = load_all_draws()
            if not draws:
                show_message("Erro", "Base de dados vazia. Execute a atualização primeiro.", True)
                return

            if advanced:
                # Pedir o tipo em thread-safe no mainloop
                tipo = ask_on_main_thread(simpledialog.askstring, "Exportação Avançada", "Tipo de análise (frequencia, pares, trios, correlacao):", parent=root)
                if not tipo: return

                if tipo not in ["frequencia", "pares", "trios", "correlacao"]:
                    show_message("Erro", "Tipo de exportação avançada não suportado.", True)
                    return

                # Pedir o caminho do arquivo no mainloop para evitar erros de GUI em background thread
                file_path = ask_on_main_thread(filedialog.asksaveasfilename, defaultextension=".csv", filetypes=[("CSV files", "*.csv")], parent=root)
                if not file_path: return

                filename_base = sanitize_filename(os.path.splitext(os.path.basename(file_path))[0])
                
                if tipo == "frequencia":
                    counter_data = Counter()
                    for _, nums in draws:
                        counter_data.update(nums)
                    export_results(counter_data.most_common(), "csv", filename_base, header=["Número", "Frequência"])
                elif tipo == "pares":
                    data = get_most_frequent_pairs(draws, 20)
                    export_results(data, "csv", filename_base, header=["Par", "Frequência"])
                elif tipo == "trios":
                    data = get_most_frequent_triplets(draws, 20)
                    export_results(data, "csv", filename_base, header=["Trio", "Frequência"])
                elif tipo == "correlacao":
                    corr = calculate_correlation(draws)
                    if corr is not None:
                        # Usar o caminho escolhido pelo usuário ao salvar a correlação
                        try:
                            corr.to_csv(file_path)
                        except Exception as e:
                            show_message("Erro", f"Falha ao salvar correlação em {file_path}: {e}", True)
                            return
                    else:
                        show_message("Erro", "Não foi possível calcular a correlação. Verifique se Pandas está instalado.", True)
                        return
                
                show_message("Exportação Avançada", f"Análise '{tipo}' exportada para {file_path}", False)

            else: # Simple export
                # Pedir caminho de saída de forma thread-safe
                file_path = ask_on_main_thread(filedialog.asksaveasfilename, defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json")], parent=root)
                if not file_path: return

                file_format = file_path.split('.')[-1]
                filename_base = sanitize_filename(os.path.splitext(os.path.basename(file_path))[0])

                export_data = []
                for d, nums in draws:
                    export_data.append([d.strftime('%Y-%m-%d')] + list(nums))

                export_results(
                    export_data,
                    file_format,
                    filename_base,
                    header=['Data'] + [f'Dezena{i+1}' for i in range(NUM_DEZENAS)]
                )
                show_message("Exportação Simples", f"Dados brutos exportados para {file_path}", False)

            open_file_location(file_path)

        except Exception as e:
            show_message("Erro na Exportação", f"Ocorreu um erro na exportação: {e}", True)
    
    run_in_thread(_export)

def update_db_gui():
    def _update():
        try:
            update_db()
            show_message("Atualização", "Base de dados atualizada com sucesso!", False)
        except Exception as e:
            show_message("Erro na Atualização", f"Ocorreu um erro ao atualizar a base de dados: {e}", True)
    
    run_in_thread(_update)

def generate_and_save_user_set_gui():
    def _generate_and_save():
        draws = load_all_draws()
        if not draws:
            show_message("Erro", "Base de dados vazia. Atualize primeiro para gerar números.", True)
            return

        method = simpledialog.askstring("Gerar Meus Números", "Escolha o método (alltime, lastyear, weighted, prediction, backtest-insights):", parent=root)
        if not method: return

        generated_numbers: Optional[List[int]] = []
        if method == "alltime":
            generated_numbers = get_most_frequent(draws)
        elif method == "lastyear":
            generated_numbers = get_most_frequent_period(draws)
        elif method == "weighted":
            generated_numbers = get_weighted(draws)
        elif method == "prediction":
            prediction = generate_smart_prediction(draws)
            generated_numbers = [num for num, _ in prediction[:6]]
        elif method == "backtest-insights":
            backtest_method = simpledialog.askstring("Método de Backtest", "Escolha o método de backtest (alltime, lastyear, weighted):", parent=root)
            if not backtest_method:
                return
            generated_numbers = get_from_backtest_insights(method=backtest_method)
        else:
            show_message("Erro", "Método de geração inválido.", True)
            return

        if not generated_numbers:
            show_message("Informação", "Não foi possível gerar números com o método selecionado.", False)
            return

        set_name = simpledialog.askstring("Salvar Meus Números", f"Números gerados: {generated_numbers}\n\nInforme um nome para este conjunto:", parent=root)
        if not set_name: return
        
        if save_user_set(set_name, generated_numbers):
            show_message("Sucesso", f"Conjunto '{set_name}' ({generated_numbers}) salvo com sucesso!", False)
            toggle_compare_button_state()
        else:
            show_message("Erro", f"Falha ao salvar o conjunto '{set_name}'. Talvez o nome já exista ou outro erro ocorreu.", True)

    run_in_thread(_generate_and_save)

def compare_user_sets_gui():
    def _compare():
        try:
            user_sets = load_user_sets()
            if user_sets:
                comparison_results = compare_user_sets_with_latest_draw()

                if not comparison_results:
                    if root:
                        root.after(0, lambda: show_message("Erro", "Não foi possível realizar a comparação. Verifique a base de dados da Mega-Sena e a conexão com a API.", True))
                    else:
                        show_message("Erro", "Não foi possível realizar a comparação. Verifique a base de dados da Mega-Sena e a conexão com a API.", True)
                    return

                latest_concurso_num = comparison_results[0].get('comparison_concurso', "N/A")
                latest_draw_dezenas = comparison_results[0].get('latest_draw_dezenas', [])

                result_display = f"Comparação com o Sorteio {latest_concurso_num} ({latest_draw_dezenas}):\n\n"
                for user_set in comparison_results:
                    set_name = user_set.get('name', 'N/A')
                    numbers = user_set.get('numbers', [])
                    comp_result = user_set.get('comparison_result', 'N/A')
                    matches = user_set.get('matches', 0)
                    result_display += f"Conjunto '{set_name}' ({numbers}): {comp_result} ({matches} acertos)\n"

                if root:
                    root.after(0, lambda rd=result_display: show_message("Resultado da Comparação", rd, False))
                else:
                    show_message("Resultado da Comparação", result_display, False)
                return

            # Se não há conjuntos salvos, pergunte ao usuário se deseja comparar manualmente
            def ask_manual():
                try:
                    ans = messagebox.askyesno("Comparar Manual", "Nenhum conjunto salvo. Deseja comparar números manualmente agora?", parent=root)
                    if not ans:
                        return

                    s = simpledialog.askstring("Comparar Manual", f"Informe {NUM_DEZENAS} números separados por vírgula (ex: 1,4,23,34,45,56):", parent=root)
                    if not s:
                        return

                    try:
                        nums = [int(x.strip()) for x in s.split(',') if x.strip() != '']
                    except ValueError:
                        show_message("Erro", "Formato inválido. Informe somente números separados por vírgula.", True)
                        return

                    if len(nums) != NUM_DEZENAS or len(set(nums)) != NUM_DEZENAS:
                        show_message("Erro", f"Informe exatamente {NUM_DEZENAS} números únicos.", True)
                        return

                    for n in nums:
                        if not (1 <= n <= MAX_NUM_MEGA_SENA):
                            show_message("Erro", f"Números devem estar entre 1 e {MAX_NUM_MEGA_SENA}.", True)
                            return

                    # Executa a comparação em thread para não bloquear a GUI
                    def do_manual_compare(numbers: List[int]):
                        try:
                            result = compare_numbers_with_latest_draw(numbers)
                            if not result:
                                if root:
                                    root.after(0, lambda: show_message("Erro", "Não foi possível obter o último sorteio para comparação.", True))
                                else:
                                    show_message("Erro", "Não foi possível obter o último sorteio para comparação.", True)
                                return

                            msg = f"Comparação com o Sorteio {result.get('comparison_concurso', 'N/A')} ({result.get('latest_draw_dezenas', [])}):\n\n"
                            msg += f"Conjunto Manual ({result.get('numbers', [])}): {result.get('comparison_result', 'N/A')} ({result.get('matches', 0)} acertos)"

                            if root:
                                root.after(0, lambda m=msg: show_message("Resultado da Comparação", m, False))
                            else:
                                show_message("Resultado da Comparação", msg, False)
                        except Exception as e:
                            if root:
                                root.after(0, lambda exc=e: show_message("Erro", f"Erro ao comparar conjunto manual: {exc}", True))
                            else:
                                show_message("Erro", f"Erro ao comparar conjunto manual: {e}", True)

                    run_in_thread(do_manual_compare, nums)
                except Exception as e:
                    show_message("Erro", f"Erro durante entrada manual: {e}", True)

            if root:
                root.after(0, ask_manual)
            else:
                show_message("Erro", "Nenhum conjunto de números salvo para comparação.", True)
        except Exception as e:
            if root:
                root.after(0, lambda exc=e: show_message("Erro", f"Erro ao comparar conjuntos: {exc}", True))
            else:
                show_message("Erro", f"Erro ao comparar conjuntos: {e}", True)

    run_in_thread(_compare)


def search_sequence_gui():
    """Solicita 6 números ao usuário e procura no histórico por essa sequência.
    Se não encontrada, mostra o sorteio com maior número de acertos."""
    s = simpledialog.askstring("Pesquisar Sequência", "Informe 6 números separados por vírgula (ex: 1,4,23,34,45,56):", parent=root)
    if not s:
        return
    try:
        nums = [int(x.strip()) for x in s.split(',') if x.strip() != '']
    except ValueError:
        show_message("Erro", "Formato inválido. Informe somente números separados por vírgula.", True)
        return

    if len(nums) != NUM_DEZENAS or len(set(nums)) != NUM_DEZENAS:
        show_message("Erro", f"Informe exatamente {NUM_DEZENAS} números únicos.", True)
        return

    for n in nums:
        if not (1 <= n <= MAX_NUM_MEGA_SENA):
            show_message("Erro", f"Números devem estar entre 1 e {MAX_NUM_MEGA_SENA}.", True)
            return

    def _search(numbers: List[int]):
        try:
            exact = find_exact_sequence(numbers)
            if exact:
                msg = f"A sequência {sorted(numbers)} foi sorteada no concurso {exact['concurso']} em {exact['data']}."
                show_message("Sequência Encontrada", msg, False)
                return

            best = find_best_match_draw(numbers)
            max_matches = best.get('max_matches', 0)
            if max_matches == 0 or not best.get('draws'):
                show_message("Resultado", "Nenhuma coincidência encontrada em um único sorteio.", False)
                return

            # Escolhe o primeiro (pode haver empates)
            draw = best['draws'][0]
            msg = (
                f"Nenhum sorteio com as 6 dezenas exatas foi encontrado.\n"
                f"Maior número de acertos em um concurso: {max_matches}.\n"
                f"Concurso {draw['concurso']} em {draw['data']}: {draw['dezenas']}"
            )
            show_message("Melhor Acerto Encontrado", msg, False)
        except Exception as e:
            show_message("Erro", f"Erro ao procurar sequência: {e}", True)

    run_in_thread(_search, nums)


def toggle_compare_button_state():
    global compare_button, compare_hint_label
    if compare_button is not None:
        user_sets = load_user_sets()
        # Mantém o botão habilitado para permitir comparação manual quando não há conjuntos salvos
        compare_button.config(state=tk.NORMAL)

        if not user_sets:
            # DX: mostrar dica clara quando não há conjuntos salvos
            if compare_hint_label is not None:
                compare_hint_label.config(text=f"Nenhum conjunto salvo — clique para comparar manualmente {NUM_DEZENAS} números")
            if hasattr(compare_button, 'tooltip'):
                compare_button.tooltip.set_text(f"Nenhum conjunto salvo — clique para comparar manualmente um conjunto de {NUM_DEZENAS} números")
            if status_bar:
                status_bar.config(text="Pronto (botão permite comparação manual quando não há conjuntos salvos)")
        else:
            if compare_hint_label is not None:
                compare_hint_label.config(text="Clique para comparar todos os seus conjuntos com o último sorteio")
            if hasattr(compare_button, 'tooltip'):
                compare_button.tooltip.set_text("Comparar seus conjuntos salvos com o último sorteio")
            if status_bar:
                status_bar.config(text="Pronto")

def run_backtest_gui(method: Optional[str] = None):
    """Permite ao usuário escolher um método e executa o backtest."""
    def _prompt_and_run():
        if not method:
            selected_method = simpledialog.askstring("Executar Backtest", "Escolha o método (alltime, lastyear, weighted):", parent=root)
            if not selected_method:
                return
        else:
            selected_method = method

        show_message("Backtest", f"Iniciando backtest para o método '{selected_method}'...", False)
        
        if run_backtest(selected_method):
            if root:
                root.after(100, lambda: show_backtest_results_gui(selected_method))
        else:
            show_message("Erro", "Ocorreu um erro ao executar o backtest.", True)

    run_in_thread(_prompt_and_run)

def show_backtest_results_gui(method: str):
    """Exibe os resultados do backtest em uma janela."""
    summary = get_backtest_summary(method)
    if not summary['numbers']:
        show_message("Erro", f"Nenhum resultado de backtest encontrado para o método '{method}'.", True)
        return

    result_text = f"Backtest para o método: '{summary['method']}'\n"
    result_text += f"Números gerados: {summary['numbers']}\n\n"
    result_text += f"Resultado contra {summary['total_draws']} sorteios históricos:\n"
    
    # Calculate total matches
    total_matches = sum(matches * count for matches, count in summary['matches'].items())
    result_text += f"\nTotal de acertos (soma de todos os números que deram match): {total_matches}\n"

    acertos_list = []
    for i in range(6, -1, -1):
        if i in summary['matches']:
            acertos_list.append(f"{i} acertos: {summary['matches'][i]} vezes")
    
    result_text += "\n" + "\n".join(acertos_list)
    
    messagebox.showinfo("Resumo do Backtest", result_text)

def show_help():
    help_text = """
    **Mega-Sena Analyzer GUI**

    - **Atualizar Base de Dados**: Busca os últimos resultados da Mega-Sena e os armazena localmente.
    - **Top 6 de Todos os Tempos**: Mostra os números sorteados com maior frequência em todo o histórico.
    - **Top 6 do Último Ano**: Identifica os números mais frequentes nos últimos 365 dias.
    - **Conjunto Estatístico Ponderado**: Sugere um conjunto de 6 números baseado na frequência histórica, dando mais peso aos números mais sorteados.
    - **Visualizar Frequência**: Abre um gráfico de barras mostrando a frequência de cada número (1 a 60).
    - **Simulação de Monte Carlo**: Simula milhares de sorteios aleatórios para comparar as frequências simuladas com as reais.
    - **Correlação**: Calcula a matriz de correlação entre os números, indicando quais números tendem a sair juntos (para exportação avançada).
    - **Séries Temporais**: Exibe um gráfico da frequência de sorteios ao longo do tempo.
    - **Distribuição de Probabilidade**: Realiza um teste Qui-quadrado para verificar se a distribuição dos números sorteados é aleatória ou se há vieses.
    - **Pares Mais Frequentes**: Lista os 10 pares de números que mais apareceram juntos.
    - **Trios Mais Frequentes**: Lista os 10 trios de números que mais apareceram juntos.
    - **Probabilidade Condicional**: Calcula a probabilidade de um número específico ser sorteado, dado que outro número já foi sorteado.
    - **Top 6 por Período**: Permite filtrar os sorteios por um intervalo de datas e ver os 6 números mais frequentes nesse período.
    - **Exportar Dados Brutos**: Exporta os dados brutos de todos os sorteios para um arquivo CSV ou JSON.
    - **Exportação Avançada**: Permite exportar análises específicas (frequência, pares, trios, correlação) para CSV.
    - **Gerar e Salvar Meus Números**: Permite escolher um método de análise e salvar o conjunto de 6 números gerado para futuras comparações.
    - **Comparar Meus Números com Último Sorteio**: Compara todos os conjuntos de números salvos com o resultado do último sorteio da Mega-Sena.
    - **Executar Backtest**: Executa uma análise retrospectiva do desempenho de uma estratégia de geração de números contra todos os sorteios históricos, salvando e exibindo um resumo dos resultados.

    **Repositório no GitHub**: Visite nosso repositório para mais informações, código-fonte e contribuições.
    """
    messagebox.showinfo("Ajuda do Mega-Sena Analyzer", help_text)

def open_github():
    webbrowser.open("https://github.com/marcosfland/mega_sena_estatistico")
    show_message("Informação", "Repositório do GitHub aberto no navegador.", False)

def show_about():
    about_text = "Mega-Sena Analyzer\nVersão 1.3 (Backtest de Estratégias)\nDesenvolvido por Marcos\n\nFerramenta de análise estatística para os sorteios da Mega-Sena."
    messagebox.showinfo("Sobre o Mega-Sena Analyzer", about_text)

def create_gui():
    global root, status_bar, compare_button

    root = tk.Tk()
    root.title("Mega-Sena Analyzer")
    root.geometry("700x950") # Aumentado para acomodar novos botões
    root.resizable(False, False)
    
    icon_path = get_resource_path("icon.png")
    if os.path.exists(icon_path) and Image:
        try:
            icon_image = tk.PhotoImage(file=icon_path)
            root.iconphoto(False, icon_image)
        except tk.TclError as e:
            logging.warning(f"Erro ao carregar ícone: {e}. Certifique-se de que 'icon.png' é um formato suportado pelo Tkinter ou Pillow está instalado.")
    else:
        # Tentar fallback embutido (pequeno GIF 1x1 transparente)
        gif_b64 = "R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
        try:
            icon_image = tk.PhotoImage(data=gif_b64)
            root.iconphoto(False, icon_image)
        except Exception as e:
            logging.warning(f"Ícone não encontrado e fallback embutido falhou: {e}. O ícone da aplicação não será exibido.")

    style = ttk.Style()
    style.theme_use('clam')

    style.configure('TFrame', background='#e0e0e0')
    style.configure('TButton', font=('Helvetica', 10, 'bold'), padding=10, background='#007BFF', foreground='white')
    style.map('TButton', background=[('active', '#0056b3')], foreground=[('active', 'white')])
    style.configure('TLabel', font=('Helvetica', 12), background='#e0e0e0', foreground='#333333')
    style.configure('TMenubutton', font=('Helvetica', 10))
    style.configure('TEntry', font=('Helvetica', 10))
    
    style.configure('Accent.TButton', background='#28a745', foreground='white')
    style.map('Accent.TButton', background=[('active', '#218838')])

    menu_bar = Menu(root)
    root.config(menu=menu_bar)

    file_menu = Menu(menu_bar, tearoff=0)
    file_menu.add_command(label="Atualizar Base de Dados", command=update_db_gui)
    file_menu.add_command(label="Exportar Dados Brutos (CSV/JSON)", command=lambda: export_data_gui(advanced=False))
    file_menu.add_command(label="Exportação Avançada (Análises)", command=lambda: export_data_gui(advanced=True))
    file_menu.add_separator()
    file_menu.add_command(label="Sair", command=root.quit)
    menu_bar.add_cascade(label="Arquivo", menu=file_menu)

    help_menu = Menu(menu_bar, tearoff=0)
    help_menu.add_command(label="Ajuda", command=show_help)
    help_menu.add_command(label="Repositório no GitHub", command=open_github)
    help_menu.add_separator()
    help_menu.add_command(label="Sobre", command=show_about)
    menu_bar.add_cascade(label="Ajuda", menu=help_menu)

    main_frame = ttk.Frame(root, padding="20 20 20 20", relief=tk.RAISED, borderwidth=2)
    main_frame.pack(fill=tk.BOTH, expand=True)

    title_label = ttk.Label(main_frame, text="Analisador Estatístico Mega-Sena", font=('Helvetica', 18, 'bold'), foreground='#0056b3')
    title_label.pack(pady=15)

    ttk.Label(main_frame, text="Escolha uma análise ou gerencie seus números:", font=('Helvetica', 11)).pack(pady=10)

    # Exibir e selecionar base de dados (persistida em mega_sena_config.ini)
    db_frame = ttk.Frame(main_frame)
    db_frame.pack(pady=5, padx=20, fill=tk.X)
    current_db = get_db_path()
    db_label = ttk.Label(db_frame, text=f"Base de Dados: {current_db}", font=('Helvetica', 9))
    db_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
    btn_select_db = ttk.Button(db_frame, text="Selecionar Base de Dados...", command=lambda: select_db_gui(db_label))
    btn_select_db.pack(side=tk.RIGHT)

    # Adicionar menu para seleção de DB também
    file_menu.add_command(label="Selecionar Base de Dados", command=lambda: select_db_gui(db_label))

    user_numbers_frame = ttk.LabelFrame(main_frame, text=" Meus Números ", padding="15 10 15 15")
    user_numbers_frame.pack(pady=10, padx=20, fill=tk.X)

    btn_generate = ttk.Button(user_numbers_frame, text="Gerar e Salvar Meus Números", command=generate_and_save_user_set_gui,
               style='Accent.TButton')
    btn_generate.pack(pady=5, fill=tk.X)

    compare_button = ttk.Button(user_numbers_frame, text="Comparar Meus Números com Último Sorteio", command=compare_user_sets_gui,
                                style='Accent.TButton')
    compare_button.pack(pady=5, fill=tk.X)

    # Rótulo explicativo para melhorar UX quando não há conjuntos salvos
    compare_hint_label = ttk.Label(user_numbers_frame, text="", font=('Helvetica', 9), foreground='#555555')
    compare_hint_label.pack(pady=2, fill=tk.X)

    # Tooltip simples para o botão de comparação
    compare_button.tooltip = Tooltip(compare_button, text="Comparar seus conjuntos salvos com o último sorteio")
    # Inicializa o estado do rótulo baseado na existência de conjuntos salvos
    if not load_user_sets():
        compare_hint_label.config(text=f"Nenhum conjunto salvo — clique para comparar manualmente {NUM_DEZENAS} números")
        compare_button.tooltip.set_text(f"Nenhum conjunto salvo — clique para comparar manualmente um conjunto de {NUM_DEZENAS} números")
    else:
        compare_hint_label.config(text="Clique para comparar todos os seus conjuntos com o último sorteio")
        compare_button.tooltip.set_text("Comparar seus conjuntos salvos com o último sorteio")

    btn_search = ttk.Button(user_numbers_frame, text="Pesquisar Sequência na História", command=search_sequence_gui,
               style='Accent.TButton')
    btn_search.pack(pady=5, fill=tk.X)

    # Registrar botões interativos para gerenciamento de estado durante processamento
    interactive_buttons.extend([btn_generate, compare_button, btn_search])
    ttk.Button(user_numbers_frame, text="Pesquisar Sequência na História", command=search_sequence_gui,
               style='Accent.TButton').pack(pady=5, fill=tk.X)
    
    root.after(100, toggle_compare_button_state)

    # Usando Notebook para organizar as análises em abas (Melhora a usabilidade)
    notebook = ttk.Notebook(main_frame)
    notebook.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

    gen_frame = ttk.Frame(notebook, padding="10 10 10 10")
    hist_frame = ttk.Frame(notebook, padding="10 10 10 10")
    adv_frame = ttk.Frame(notebook, padding="10 10 10 10")

    notebook.add(gen_frame, text="Geração")
    notebook.add(hist_frame, text="Estatísticas Históricas")
    notebook.add(adv_frame, text="Avançadas")

    # Registrar botões das abas (serão preenchidos abaixo) para permitir gerenciamento de estado
    # (apenas será feito logo após criação dos botões)
    # interactive_buttons estendido ao criar cada botão abaixo

    # Aba Geração: sugestões e predições
    gen_buttons = [
        ("Top 6 de Todos os Tempos", "alltime"),
        ("Top 6 do Último Ano", "lastyear"),
        ("Conjunto Estatístico Ponderado", "weighted"),
        ("Predição Inteligente", "prediction"),
        ("Top 6 por Período", "period"),
    ]

    for idx, (text, opt) in enumerate(gen_buttons):
        btn = ttk.Button(gen_frame, text=text, command=lambda o=opt: run_analysis_gui(o))
        btn.grid(row=idx // 2, column=idx % 2, padx=6, pady=6, sticky="ew")
        interactive_buttons.append(btn)

    gen_frame.grid_columnconfigure(0, weight=1)
    gen_frame.grid_columnconfigure(1, weight=1)

    # Aba Estatísticas Históricas: frequência, pares, trios, ciclos, sequências, gaps
    hist_buttons = [
        ("Visualizar Frequência", "plot"),
        ("Pares Mais Frequentes", "pairs"),
        ("Trios Mais Frequentes", "triplets"),
        ("Padrões Cíclicos", "cycles"),
        ("Análise de Intervalos", "gaps"),
        ("Análise de Sequências", "sequences"),
    ]

    for idx, (text, opt) in enumerate(hist_buttons):
        btn = ttk.Button(hist_frame, text=text, command=lambda o=opt: run_analysis_gui(o))
        btn.grid(row=idx // 2, column=idx % 2, padx=6, pady=6, sticky="ew")
        interactive_buttons.append(btn)

    hist_frame.grid_columnconfigure(0, weight=1)
    hist_frame.grid_columnconfigure(1, weight=1)

    # Aba Avançadas: Monte Carlo, Correlação, Timeseries, Distribuição, Condicional, Backtest
    adv_buttons = [
        ("Simulação de Monte Carlo", "montecarlo"),
        ("Correlação", "correlation"),
        ("Séries Temporais", "timeseries"),
        ("Distribuição de Probabilidade", "distribution"),
        ("Probabilidade Condicional", "conditional"),
        ("Backtest Insights", "backtest-insights"),
    ]

    for idx, (text, opt) in enumerate(adv_buttons):
        btn = ttk.Button(adv_frame, text=text, command=lambda o=opt: run_analysis_gui(o))
        btn.grid(row=idx // 2, column=idx % 2, padx=6, pady=6, sticky="ew")
        interactive_buttons.append(btn)

    adv_frame.grid_columnconfigure(0, weight=1)
    adv_frame.grid_columnconfigure(1, weight=1)

    # --- Nova seção de Backtesting ---
    backtest_frame = ttk.LabelFrame(main_frame, text=" Backtest de Estratégias ", padding="15 10 15 15")
    backtest_frame.pack(pady=10, padx=20, fill=tk.X)

    backtest_options_frame = ttk.Frame(backtest_frame)
    backtest_options_frame.pack(fill=tk.X, pady=5)
    
    # Dropdown para selecionar o método de backtest
    method_var = tk.StringVar(value="alltime")
    methods = ["alltime", "lastyear", "weighted"]
    method_menu = ttk.OptionMenu(backtest_options_frame, method_var, methods[0], *methods)
    method_menu.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    btn_backtest = ttk.Button(backtest_options_frame, text="Executar Backtest", command=lambda: run_backtest_gui(method_var.get()), style='Accent.TButton')
    btn_backtest.pack(side=tk.LEFT, padx=5)

    # Registrar botão de backtest
    interactive_buttons.append(btn_backtest)

    # --- Área de Resultados (Treeview) ---
    results_frame = ttk.LabelFrame(main_frame, text=" Resultados ", padding="10 10 10 10")
    results_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

    # Treeview para exibir resultados em formato tabular
    global results_tree, current_results_data, current_results_headers
    results_tree = ttk.Treeview(results_frame, columns=(), show='headings')
    results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    results_scroll = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=results_tree.yview)
    results_tree.configure(yscrollcommand=results_scroll.set)
    results_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    btn_export_results = ttk.Button(results_frame, text="Exportar Resultados", command=lambda: export_results_gui(), style='TButton')
    btn_export_results.pack(side=tk.BOTTOM, pady=6)

    # Inicializar variáveis de resultados
    current_results_data = []
    current_results_headers = []

    # Canvas Matplotlib embutido (opcional)
    global mpl_canvas
    mpl_canvas = None
    # Barra de progresso para operações longas
    global progress_bar
    progress_bar = ttk.Progressbar(root, mode='indeterminate')
    progress_bar.pack(side=tk.BOTTOM, fill=tk.X)

    status_bar = ttk.Label(root, text="Pronto", relief=tk.SUNKEN, anchor=tk.W, font=('Helvetica', 9), background='#f0f0f0', foreground='#555555')
    status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    root.mainloop()

def get_resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base_path, relative_path)

if __name__ == "__main__":
    if not os.path.exists(get_resource_path("icon.png")):
        try:
            if Image and ImageDraw:
                img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                draw.ellipse((2, 2, 30, 30), fill='#FFD700', outline='#DAA520')
                draw.text((8, 8), "M", fill="#4B0082", font=None)
                img.save("icon.png")
            else:
                logging.warning("Pillow não está instalado. Não é possível criar um ícone temporário. O ícone da aplicação será pulado.")
        except Exception as e:
            logging.warning(f"Falha ao criar ícone temporário: {e}")

    create_gui()

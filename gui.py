import tkinter as tk
from tkinter import messagebox, filedialog, Menu, simpledialog, ttk
from mega_sena_app import (
    load_all_draws, get_most_frequent, get_most_frequent_period,
    get_weighted, monte_carlo_simulation, plot_frequency,
    calculate_correlation, analyze_time_series, analyze_probability_distribution,
    update_db, export_results, get_most_frequent_pairs, get_most_frequent_triplets,
    conditional_probability, filter_draws_by_period, sanitize_filename,
    save_user_set, load_user_sets, delete_user_set, compare_user_sets_with_latest_draw,
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
from typing import Optional, List
try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None
    ImageDraw = None
    logging.warning("Pillow não está instalado. O ícone da aplicação pode não ser exibido.")

logging.basicConfig(filename="gui_actions.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

root = None
status_bar = None
compare_button = None # Declare compare_button globally here

def show_message(title, message, is_error=False):
    if status_bar:
        status_bar.config(text=message)
    if is_error:
        logging.error(f"{title}: {message}")
        messagebox.showerror(title, message)
    else:
        logging.info(f"{title}: {message}")
        messagebox.showinfo(title, message)
    if root and status_bar:
        root.after(5000, lambda: status_bar.config(text="Pronto") if status_bar is not None else None)

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

def run_analysis_gui(option):
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
                formatted_pairs = "\n".join([f"{pair}: {freq}" for pair, freq in result])
                result_message = f"Pares Mais Frequentes (Top 10):\n{formatted_pairs}"
            elif option == "triplets":
                result = get_most_frequent_triplets(draws, 10)
                formatted_triplets = "\n".join([f"{triplet}: {freq}" for triplet, freq in result])
                result_message = f"Trios Mais Frequentes (Top 10):\n{formatted_triplets}"
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
            
            if plot_needed:
                if option == "plot":
                    plot_frequency(draws)
                elif option == "timeseries":
                    analyze_time_series(draws)
                show_message("Gráfico Exibido", "Verifique a janela do gráfico.", False)
            else:
                show_message("Análise Concluída", result_message, False)

        except Exception as e:
            show_message("Erro na Análise", f"Ocorreu um erro ao executar a análise '{option}': {e}", True)
    
    run_in_thread(_run)

def export_data_gui(advanced=False):
    def _export():
        try:
            draws = load_all_draws()
            if not draws:
                show_message("Erro", "Base de dados vazia. Execute a atualização primeiro.", True)
                return

            if advanced:
                tipo = simpledialog.askstring("Exportação Avançada", "Tipo de análise (frequencia, pares, trios, correlacao):", parent=root)
                if not tipo: return

                if tipo not in ["frequencia", "pares", "trios", "correlacao"]:
                    show_message("Erro", "Tipo de exportação avançada não suportado.", True)
                    return

                file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")], parent=root)
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
                        corr.to_csv(f"{filename_base}.csv")
                    else:
                        show_message("Erro", "Não foi possível calcular a correlação. Verifique se Pandas está instalado.", True)
                        return
                
                show_message("Exportação Avançada", f"Análise '{tipo}' exportada para {file_path}", False)

            else: # Simple export
                file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json")], parent=root)
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

        method = simpledialog.askstring("Gerar Meus Números", "Escolha o método (alltime, lastyear, weighted):", parent=root)
        if not method: return

        generated_numbers: Optional[List[int]] = []
        if method == "alltime":
            generated_numbers = get_most_frequent(draws)
        elif method == "lastyear":
            generated_numbers = get_most_frequent_period(draws)
        elif method == "weighted":
            generated_numbers = get_weighted(draws)
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
            toggle_compare_button_state() # Ensure button state is updated
        else:
            show_message("Erro", f"Falha ao salvar o conjunto '{set_name}'. Talvez o nome já exista ou outro erro ocorreu.", True)

    run_in_thread(_generate_and_save)

def compare_user_sets_gui():
    def _compare():
        user_sets = load_user_sets()
        if not user_sets:
            show_message("Erro", "Nenhum conjunto de números salvo para comparação.", True)
            return

        comparison_results = compare_user_sets_with_latest_draw()

        if not comparison_results:
            show_message("Erro", "Não foi possível realizar a comparação. Verifique a base de dados da Mega-Sena e a conexão com a API.", True)
            return
        
        # Access latest_concurso_num and latest_draw_dezenas more safely
        latest_concurso_num = comparison_results[0].get('comparison_concurso', "N/A")
        latest_draw_dezenas = comparison_results[0].get('latest_draw_dezenas', [])


        result_display = f"Comparação com o Sorteio {latest_concurso_num} ({latest_draw_dezenas}):\n\n"
        for user_set in comparison_results:
            # Safely get values, providing defaults if keys might be missing (though they should be present after comparison)
            set_name = user_set.get('name', 'N/A')
            numbers = user_set.get('numbers', [])
            comp_result = user_set.get('comparison_result', 'N/A')
            matches = user_set.get('matches', 0)
            result_display += f"Conjunto '{set_name}' ({numbers}): {comp_result} ({matches} acertos)\n"
        
        show_message("Resultado da Comparação", result_display, False)

    run_in_thread(_compare)

def toggle_compare_button_state():
    global compare_button
    if compare_button is not None: # Check if the button has been created
        user_sets = load_user_sets()
        if user_sets:
            compare_button.config(state=tk.NORMAL)
        else:
            compare_button.config(state=tk.DISABLED)

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

    **Repositório no GitHub**: Visite nosso repositório para mais informações, código-fonte e contribuições.
    """
    messagebox.showinfo("Ajuda do Mega-Sena Analyzer", help_text)

def open_github():
    webbrowser.open("https://github.com/marcosfland/mega_sena_estatistico")
    show_message("Informação", "Repositório do GitHub aberto no navegador.", False)

def show_about():
    about_text = "Mega-Sena Analyzer\nVersão 1.2 (Gerenciamento de Números Pessoais)\nDesenvolvido por Marcos\n\nFerramenta de análise estatística para os sorteios da Mega-Sena."
    messagebox.showinfo("Sobre o Mega-Sena Analyzer", about_text)

def create_gui():
    global root, status_bar, compare_button

    root = tk.Tk()
    root.title("Mega-Sena Analyzer")
    root.geometry("650x850")
    root.resizable(False, False)
    
    icon_path = get_resource_path("icon.png")
    if os.path.exists(icon_path) and Image:
        try:
            icon_image = tk.PhotoImage(file=icon_path)
            root.iconphoto(False, icon_image)
        except tk.TclError as e:
            logging.warning(f"Erro ao carregar ícone: {e}. Certifique-se de que 'icon.png' é um formato suportado pelo Tkinter ou Pillow está instalado.")
    else:
        logging.warning("Ícone 'icon.png' não encontrado ou Pillow não instalado. O ícone da aplicação não será exibido.")

    style = ttk.Style()
    style.theme_use('clam')

    style.configure('TFrame', background='#e0e0e0')
    style.configure('TButton', font=('Helvetica', 10, 'bold'), padding=10, background='#007BFF', foreground='white')
    style.map('TButton', background=[('active', '#0056b3')], foreground=[('active', 'white')])
    style.configure('TLabel', font=('Helvetica', 12), background='#e0e0e0', foreground='#333333')
    style.configure('TMenubutton', font=('Helvetica', 10))
    style.configure('TEntry', font=('Helvetica', 10))
    
    # Define a distinct style for the user numbers buttons
    style.configure('Accent.TButton', background='#28a745', foreground='white') # Green
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

    # --- Botões de Gerenciamento de Números (Novo Frame) ---
    user_numbers_frame = ttk.LabelFrame(main_frame, text=" Meus Números ", padding="15 10 15 15")
    user_numbers_frame.pack(pady=10, padx=20, fill=tk.X) # Pack the LabelFrame

    ttk.Button(user_numbers_frame, text="Gerar e Salvar Meus Números", command=generate_and_save_user_set_gui,
               style='Accent.TButton').pack(pady=5, fill=tk.X)
    
    compare_button = ttk.Button(user_numbers_frame, text="Comparar Meus Números com Último Sorteio", command=compare_user_sets_gui,
                                style='Accent.TButton', state=tk.DISABLED)
    compare_button.pack(pady=5, fill=tk.X)
    
    # Ensure this is called AFTER compare_button is initialized
    root.after(100, toggle_compare_button_state) # Call after a short delay to ensure GUI is ready

    # --- Botões de Análise (Organizados em Grid) ---
    analysis_frame = ttk.LabelFrame(main_frame, text=" Análises Estatísticas ", padding="15 10 15 15")
    analysis_frame.pack(pady=10, padx=20, fill=tk.X) # Pack the LabelFrame

    button_configs = [
        ("Top 6 de Todos os Tempos", "alltime"),
        ("Top 6 do Último Ano", "lastyear"),
        ("Conjunto Estatístico Ponderado", "weighted"),
        ("Visualizar Frequência", "plot"),
        ("Simulação de Monte Carlo", "montecarlo"),
        ("Correlação", "correlation"),
        ("Séries Temporais", "timeseries"),
        ("Distribuição de Probabilidade", "distribution"),
        ("Pares Mais Frequentes", "pairs"),
        ("Trios Mais Frequentes", "triplets"),
        ("Probabilidade Condicional", "conditional"),
        ("Top 6 por Período", "period"),
    ]

    row_idx = 0
    col_idx = 0
    for text, option in button_configs:
        button = ttk.Button(analysis_frame, text=text, command=lambda opt=option: run_analysis_gui(opt))
        button.grid(row=row_idx, column=col_idx, padx=5, pady=5, sticky="ew")
        col_idx += 1
        if col_idx > 1:
            col_idx = 0
            row_idx += 1
    
    analysis_frame.grid_columnconfigure(0, weight=1)
    analysis_frame.grid_columnconfigure(1, weight=1)

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
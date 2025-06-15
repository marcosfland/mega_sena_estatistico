import tkinter as tk
from tkinter import messagebox, filedialog, Menu, simpledialog, ttk # Import ttk for themed widgets
from mega_sena_app import (
    load_all_draws, get_most_frequent, get_most_frequent_period,
    get_weighted, monte_carlo_simulation, plot_frequency,
    calculate_correlation, analyze_time_series, analyze_probability_distribution,
    update_db, export_results, get_most_frequent_pairs, get_most_frequent_triplets,
    conditional_probability, filter_draws_by_period, sanitize_filename
)
import webbrowser
from collections import Counter
import os
import datetime
import logging
import subprocess
import threading # For running long tasks in the background

# --- Configuração de Logging ---
logging.basicConfig(filename="gui_actions.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Funções Auxiliares para a GUI ---

def show_message(title, message, is_error=False):
    """Exibe uma messagebox e atualiza o status bar."""
    status_bar.config(text=message)
    if is_error:
        logging.error(message)
        messagebox.showerror(title, message)
    else:
        logging.info(message)
        messagebox.showinfo(title, message)
    # Clear status bar after a short delay
    root.after(5000, lambda: status_bar.config(text="Pronto"))

def open_file_location(filepath):
    """Abre o explorador de arquivos na pasta do arquivo exportado."""
    try:
        folder = os.path.dirname(os.path.abspath(filepath))
        if os.name == 'nt':  # Windows
            os.startfile(folder)
        elif os.name == 'posix':  # Linux/macOS
            subprocess.Popen(['xdg-open', folder])
    except Exception as e:
        show_message("Erro", f"Não foi possível abrir o local do arquivo: {e}", True)

def run_in_thread(func, *args, **kwargs):
    """Executa uma função em uma thread separada para evitar que a GUI congele."""
    status_bar.config(text="Processando... Por favor, aguarde.")
    thread = threading.Thread(target=lambda: func(*args, **kwargs))
    thread.start()

# --- Funções de Lógica de Negócios (adaptadas para a GUI) ---

def run_analysis_gui(option):
    """Wrapper para executar as análises e exibir resultados na GUI."""
    def _run():
        try:
            draws = load_all_draws()
            if not draws:
                show_message("Erro", "Base de dados vazia. Execute a atualização primeiro.", True)
                return

            result_message = ""
            plot_needed = False
            correlation_needed = False

            if option == "alltime":
                result = get_most_frequent(draws)
                result_message = f"Top 6 de Todos os Tempos: {result}"
            elif option == "lastyear":
                result = get_most_frequent_period(draws)
                if not result:
                    result_message = "Nenhum sorteio encontrado no último ano para análise."
                else:
                    result_message = f"Top 6 do Último Ano: {result}"
            elif option == "weighted":
                result = get_weighted(draws)
                result_message = f"Conjunto Estatístico Ponderado: {result}"
            elif option == "plot":
                plot_needed = True
            elif option == "montecarlo":
                simulated, real = monte_carlo_simulation(draws)
                result_message = f"Simulação de Monte Carlo - Números Mais Frequentes:\nSimulados (Número, Frequência): {simulated}\nReais (Número, Frequência): {real}"
            elif option == "correlation":
                correlation_needed = True # Handle correlation separately for display
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
                # Format pairs nicely for display
                formatted_pairs = "\n".join([f"{pair}: {freq}" for pair, freq in result])
                result_message = f"Pares Mais Frequentes (Top 10):\n{formatted_pairs}"
            elif option == "triplets":
                result = get_most_frequent_triplets(draws, 10)
                # Format triplets nicely for display
                formatted_triplets = "\n".join([f"{triplet}: {freq}" for triplet, freq in result])
                result_message = f"Trios Mais Frequentes (Top 10):\n{formatted_triplets}"
            elif option == "conditional":
                given = simpledialog.askinteger("Probabilidade Condicional", "Informe o número dado (GIVEN):", parent=root)
                if given is None: return # User cancelled
                target = simpledialog.askinteger("Probabilidade Condicional", "Informe o número alvo (TARGET):", parent=root)
                if target is None: return # User cancelled

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
                        result_message = f"Top 6 no Período ({start} a {end}): {result}"
                except ValueError as e:
                    show_message("Erro", f"Formato de data inválido. Use AAAA-MM-DD. Erro: {e}", True)
                    return
            
            if plot_needed:
                if option == "plot":
                    plot_frequency(draws)
                elif option == "timeseries":
                    analyze_time_series(draws)
                show_message("Gráfico Exibido", "Verifique a janela do gráfico.", False)
            elif correlation_needed:
                correlation_matrix = calculate_correlation(draws)
                if correlation_matrix is not None:
                    # Displaying large matrices in messagebox is not ideal.
                    # Suggesting to export or show a snippet.
                    show_message("Correlação", "Matriz de Correlação calculada. Para visualização completa, use a 'Exportação Avançada'.", False)
                else:
                    show_message("Erro", "Não foi possível calcular a correlação. Verifique se Pandas está instalado.", True)
            else:
                show_message("Análise Concluída", result_message, False)

        except Exception as e:
            show_message("Erro na Análise", f"Ocorreu um erro ao executar a análise '{option}': {e}", True)
    
    run_in_thread(_run) # Run analysis in a separate thread

def export_data_gui(advanced=False):
    """
    Função unificada para exportação simples e avançada.
    Se 'advanced' for True, solicita tipo de análise para exportar.
    """
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

                # Prepare data for simple export (raw draws)
                export_data = []
                for d, nums in draws:
                    export_data.append([d.strftime('%Y-%m-%d')] + list(nums))
                
                export_results(
                    export_data,
                    file_format,
                    filename_base,
                    header=['Data'] + [f'Dezena{i+1}' for i in range(len(draws[0][1]))] # Dynamic header based on num dezenas
                )
                show_message("Exportação Simples", f"Dados brutos exportados para {file_path}", False)

            open_file_location(file_path)

        except Exception as e:
            show_message("Erro na Exportação", f"Ocorreu um erro na exportação: {e}", True)
    
    run_in_thread(_export)

def update_db_gui():
    """Atualiza a base de dados via GUI."""
    def _update():
        try:
            update_db()
            show_message("Atualização", "Base de dados atualizada com sucesso!", False)
        except Exception as e:
            show_message("Erro na Atualização", f"Ocorreu um erro ao atualizar a base de dados: {e}", True)
    
    run_in_thread(_update)

def show_help():
    """Exibe informações de ajuda."""
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
    - **Exportar Dados**: Exporta os dados brutos de todos os sorteios para um arquivo CSV ou JSON.
    - **Exportação Avançada**: Permite exportar análises específicas (frequência, pares, trios, correlação) para CSV.

    **Repositório no GitHub**: Visite nosso repositório para mais informações, código-fonte e contribuições.
    """
    messagebox.showinfo("Ajuda do Mega-Sena Analyzer", help_text)

def open_github():
    """Abre o repositório do GitHub no navegador padrão."""
    webbrowser.open("https://github.com/marcosfland/mega_sena_estatistico")
    show_message("Informação", "Repositório do GitHub aberto no navegador.", False)

def show_about():
    """Exibe informações sobre o aplicativo."""
    about_text = "Mega-Sena Analyzer\nVersão 1.1 (GUI Aprimorada)\nDesenvolvido por Marcos\n\nFerramenta de análise estatística para os sorteios da Mega-Sena."
    messagebox.showinfo("Sobre o Mega-Sena Analyzer", about_text)

# --- Criação da Interface Gráfica (GUI) ---

def create_gui():
    global root, status_bar # Make root and status_bar accessible globally for updates

    root = tk.Tk()
    root.title("Mega-Sena Analyzer")
    root.geometry("600x750") # Adjust window size for better layout
    root.resizable(False, False) # Prevent resizing for simplicity
    root.iconphoto(False, tk.PhotoImage(file=get_resource_path("icon.png"))) # Optional: Add an icon

    # Theme configuration
    style = ttk.Style()
    style.theme_use('clam') # 'clam', 'alt', 'default', 'classic'

    style.configure('TFrame', background='#e0e0e0')
    style.configure('TButton', font=('Helvetica', 10), padding=10, background='#4CAF50', foreground='white')
    style.map('TButton', background=[('active', '#45a049')])
    style.configure('TLabel', font=('Helvetica', 12), background='#e0e0e0', foreground='#333333')
    style.configure('TMenubutton', font=('Helvetica', 10))
    style.configure('TEntry', font=('Helvetica', 10))

    # --- Menu Superior ---
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

    # --- Frame Principal ---
    main_frame = ttk.Frame(root, padding="20 20 20 20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Título
    title_label = ttk.Label(main_frame, text="Analisador Estatístico Mega-Sena", font=('Helvetica', 16, 'bold'), foreground='#0056b3')
    title_label.pack(pady=10)

    ttk.Label(main_frame, text="Escolha uma análise para visualizar ou exportar:", font=('Helvetica', 10)).pack(pady=5)

    # --- Botões de Análise (Organizados em Grid) ---
    analysis_frame = ttk.Frame(main_frame, padding="10 0 10 0")
    analysis_frame.pack(pady=10, fill=tk.X)

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

    # Use a grid layout for buttons for better organization
    row_idx = 0
    col_idx = 0
    for text, option in button_configs:
        button = ttk.Button(analysis_frame, text=text, command=lambda opt=option: run_analysis_gui(opt))
        button.grid(row=row_idx, column=col_idx, padx=5, pady=5, sticky="ew") # sticky="ew" makes buttons expand horizontally
        col_idx += 1
        if col_idx > 1: # 2 buttons per row
            col_idx = 0
            row_idx += 1
    
    # Configure grid columns to expand evenly
    analysis_frame.grid_columnconfigure(0, weight=1)
    analysis_frame.grid_columnconfigure(1, weight=1)

    # --- Status Bar ---
    status_bar = ttk.Label(root, text="Pronto", relief=tk.SUNKEN, anchor=tk.W, font=('Helvetica', 9))
    status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    root.mainloop()

# --- Helper to get resource path for packaging ---
def get_resource_path(relative_path):
    """Obtém o caminho absoluto para um recurso."""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))  # Use _MEIPASS if it exists, else current dir
    return os.path.join(base_path, relative_path)

import sys # Import sys for PyInstaller compatibility

if __name__ == "__main__":
    # Create a dummy icon.png if it doesn't exist for testing.
    # In a real deployment, you'd include a proper icon file.
    if not os.path.exists("icon.png"):
        try:
            # Create a simple 32x32 transparent PNG (requires Pillow)
            from PIL import Image, ImageDraw
            img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse((2, 2, 30, 30), fill='lightgreen', outline='darkgreen')
            draw.text((8, 8), "MS", fill="darkblue", font=None) # A simple text for an icon
            img.save("icon.png")
        except ImportError:
            logging.warning("Pillow not installed. Cannot create a dummy icon. 'icon.png' will be skipped.")
        except Exception as e:
            logging.warning(f"Failed to create dummy icon: {e}")

    create_gui()
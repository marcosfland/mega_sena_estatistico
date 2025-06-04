import tkinter as tk
from tkinter import messagebox, filedialog, Menu, simpledialog
from mega_sena_app import (
    load_all_draws, get_most_frequent, get_most_frequent_period,
    get_weighted, monte_carlo_simulation, plot_frequency,
    calculate_correlation, analyze_time_series, analyze_probability_distribution,
    update_db, export_results, get_most_frequent_pairs, get_most_frequent_triplets,
    conditional_probability, filter_draws_by_period, export_advanced_v2, sanitize_filename
)
import webbrowser
from collections import Counter
import os
import datetime
import logging
import subprocess

# Configuração de logging para ações do usuário
logging.basicConfig(filename="gui_actions.log", level=logging.INFO, format="%(asctime)s %(message)s")

def run_analysis(option):
    try:
        draws = load_all_draws()
        if not draws:
            messagebox.showerror("Erro", "Base de dados vazia. Execute a atualização primeiro.")
            return

        if option == "alltime":
            result = get_most_frequent(draws)
            messagebox.showinfo("Top 6 de Todos os Tempos", f"Números: {result}")
        elif option == "lastyear":
            result = get_most_frequent_period(draws)
            messagebox.showinfo("Top 6 do Último Ano", f"Números: {result}")
        elif option == "weighted":
            result = get_weighted(draws)
            messagebox.showinfo("Conjunto Estatístico Ponderado", f"Números: {result}")
        elif option == "plot":
            plot_frequency(draws)
        elif option == "montecarlo":
            simulated, real = monte_carlo_simulation(draws)
            messagebox.showinfo("Monte Carlo", f"Simulados: {simulated}\nReais: {real}")
        elif option == "correlation":
            correlation_matrix = calculate_correlation(draws)
            messagebox.showinfo("Correlação", f"Matriz de Correlação:\n{correlation_matrix}")
        elif option == "timeseries":
            analyze_time_series(draws)
        elif option == "distribution":
            chi2, p = analyze_probability_distribution(draws)
            messagebox.showinfo("Distribuição de Probabilidade", f"Chi2: {chi2}, p-valor: {p}")
        elif option == "pairs":
            result = get_most_frequent_pairs(draws, 10)
            messagebox.showinfo("Pares Mais Frequentes", f"{result}")
        elif option == "triplets":
            result = get_most_frequent_triplets(draws, 10)
            messagebox.showinfo("Trios Mais Frequentes", f"{result}")
        elif option == "conditional":
            given = simpledialog.askinteger("Probabilidade Condicional", "Informe o número dado (GIVEN):")
            target = simpledialog.askinteger("Probabilidade Condicional", "Informe o número alvo (TARGET):")
            if given is not None and target is not None:
                prob = conditional_probability(draws, given, target)
                messagebox.showinfo("Probabilidade Condicional", f"P({target}|{given}) = {prob:.4f}")
        elif option == "period":
            start = simpledialog.askstring("Filtro por Período", "Data inicial (YYYY-MM-DD):")
            end = simpledialog.askstring("Filtro por Período", "Data final (YYYY-MM-DD):")
            if not start or not end:
                messagebox.showerror("Erro", "Datas não podem ser vazias.")
                return
            try:
                start_date = datetime.datetime.strptime(start, "%Y-%m-%d").date()
                end_date = datetime.datetime.strptime(end, "%Y-%m-%d").date()
                filtered = filter_draws_by_period(draws, start_date, end_date)
                if not filtered:
                    messagebox.showinfo("Sem Resultados", "Nenhum sorteio encontrado no período informado.")
                    return
                result = get_most_frequent(filtered)
                messagebox.showinfo("Top 6 no Período", f"Números: {result}")
            except Exception as e:
                messagebox.showerror("Erro", f"Datas inválidas: {e}")
        logging.info(f"Análise executada: {option}")
    except Exception as e:
        logging.error(f"Erro ao executar análise {option}: {e}")
        messagebox.showerror("Erro", f"Ocorreu um erro: {e}")

def export_data():
    try:
        draws = load_all_draws()
        if not draws:
            messagebox.showerror("Erro", "Base de dados vazia. Execute a atualização primeiro.")
            return

        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json")])
        if file_path:
            file_format = file_path.split('.')[-1]
            export_results(draws, file_format, file_path.rsplit('.', 1)[0])
            messagebox.showinfo("Exportação", f"Dados exportados para {file_path}")
            open_file_location(file_path)
        logging.info(f"Exportação simples realizada: {file_path}")
    except Exception as e:
        logging.error(f"Erro na exportação simples: {e}")
        messagebox.showerror("Erro", f"Ocorreu um erro na exportação: {e}")

def export_advanced_gui():
    try:
        draws = load_all_draws()
        if not draws:
            messagebox.showerror("Erro", "Base de dados vazia. Execute a atualização primeiro.")
            return
        tipo = simpledialog.askstring("Exportação Avançada", "Tipo (frequencia, pares, trios, correlacao):")
        arquivo = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not tipo or not arquivo:
            return
        nome = sanitize_filename(os.path.splitext(os.path.basename(arquivo))[0])
        if tipo == "frequencia":
            data = Counter()
            for _, nums in draws:
                data.update(nums)
            export_advanced_v2(data.most_common(), "csv", nome, header=["Número", "Frequência"])
        elif tipo == "pares":
            data = get_most_frequent_pairs(draws, 20)
            export_advanced_v2(data, "csv", nome, header=["Par", "Frequência"])
        elif tipo == "trios":
            data = get_most_frequent_triplets(draws, 20)
            export_advanced_v2(data, "csv", nome, header=["Trio", "Frequência"])
        elif tipo == "correlacao":
            corr = calculate_correlation(draws)
            corr.to_csv(f"{nome}.csv")
        else:
            messagebox.showerror("Erro", "Tipo de exportação não suportado.")
            return
        messagebox.showinfo("Exportação", f"Dados exportados para {nome}.csv")
        open_file_location(f"{nome}.csv")
        logging.info(f"Exportação avançada realizada: {tipo} em {nome}.csv")
    except Exception as e:
        logging.error(f"Erro na exportação avançada: {e}")
        messagebox.showerror("Erro", f"Ocorreu um erro na exportação avançada: {e}")

def open_file_location(filepath):
    # Abre o explorador de arquivos na pasta do arquivo exportado
    try:
        folder = os.path.dirname(os.path.abspath(filepath))
        if os.name == 'nt':
            os.startfile(folder)
        elif os.name == 'posix':
            subprocess.Popen(['xdg-open', folder])
    except Exception as e:
        logging.warning(f"Não foi possível abrir o local do arquivo: {e}")

def update_db_gui():
    try:
        update_db()
        messagebox.showinfo("Atualização", "Base de dados atualizada com sucesso!")
        logging.info("Base de dados atualizada pelo usuário.")
    except Exception as e:
        logging.error(f"Erro ao atualizar base de dados: {e}")
        messagebox.showerror("Erro", f"Ocorreu um erro ao atualizar a base: {e}")

def show_help():
    help_text = """
    - Atualizar Base de Dados: Atualiza os resultados da Mega-Sena.
    - Top 6 de Todos os Tempos: Mostra os números mais frequentes em todos os sorteios.
    - Top 6 do Último Ano: Mostra os números mais frequentes nos últimos 365 dias.
    - Conjunto Estatístico Ponderado: Calcula números baseados em ponderação estatística.
    - Visualizar Frequência: Exibe um gráfico de frequência dos números sorteados.
    - Simulação de Monte Carlo: Simula sorteios para estimar números frequentes.
    - Correlação: Calcula a correlação entre os números sorteados.
    - Séries Temporais: Exibe a tendência de sorteios ao longo do tempo.
    - Distribuição de Probabilidade: Realiza um teste qui-quadrado para verificar a uniformidade.
    - Exportar Resultados: Exporta os dados para arquivos CSV ou JSON.
    - Exportação Avançada: Exporta pares, trios, frequência ou correlação.
    """
    messagebox.showinfo("Ajuda", help_text)

def open_github():
    webbrowser.open("https://github.com/marcosfland/mega_sena_estatistico")

def show_about():
    about_text = "Mega-Sena Estatístico\nVersão 1.0\nDesenvolvido por Marcos\nAnálise estatística de sorteios da Mega-Sena."
    messagebox.showinfo("Sobre", about_text)

def create_gui():
    root = tk.Tk()
    root.title("Mega-Sena Analyzer")

    # Menu superior
    menu_bar = Menu(root)
    root.config(menu=menu_bar)

    # Menu Arquivo
    file_menu = Menu(menu_bar, tearoff=0)
    file_menu.add_command(label="Atualizar Base de Dados", command=update_db_gui)
    file_menu.add_command(label="Exportar Dados", command=export_data)
    file_menu.add_command(label="Exportação Avançada", command=export_advanced_gui)
    file_menu.add_separator()
    file_menu.add_command(label="Sair", command=root.quit)
    menu_bar.add_cascade(label="Arquivo", menu=file_menu)

    # Menu Ajuda
    help_menu = Menu(menu_bar, tearoff=0)
    help_menu.add_command(label="Ajuda", command=show_help)
    help_menu.add_command(label="Repositório no GitHub", command=open_github)
    help_menu.add_command(label="Sobre", command=show_about)
    menu_bar.add_cascade(label="Ajuda", menu=help_menu)

    # Botões principais
    tk.Label(root, text="Escolha uma análise:").pack(pady=10)

    tk.Button(root, text="Top 6 de Todos os Tempos", command=lambda: run_analysis("alltime")).pack(pady=5)
    tk.Button(root, text="Top 6 do Último Ano", command=lambda: run_analysis("lastyear")).pack(pady=5)
    tk.Button(root, text="Conjunto Estatístico Ponderado", command=lambda: run_analysis("weighted")).pack(pady=5)
    tk.Button(root, text="Visualizar Frequência", command=lambda: run_analysis("plot")).pack(pady=5)
    tk.Button(root, text="Simulação de Monte Carlo", command=lambda: run_analysis("montecarlo")).pack(pady=5)
    tk.Button(root, text="Correlação", command=lambda: run_analysis("correlation")).pack(pady=5)
    tk.Button(root, text="Séries Temporais", command=lambda: run_analysis("timeseries")).pack(pady=5)
    tk.Button(root, text="Distribuição de Probabilidade", command=lambda: run_analysis("distribution")).pack(pady=5)
    tk.Button(root, text="Pares Mais Frequentes", command=lambda: run_analysis("pairs")).pack(pady=5)
    tk.Button(root, text="Trios Mais Frequentes", command=lambda: run_analysis("triplets")).pack(pady=5)
    tk.Button(root, text="Probabilidade Condicional", command=lambda: run_analysis("conditional")).pack(pady=5)
    tk.Button(root, text="Top 6 por Período", command=lambda: run_analysis("period")).pack(pady=5)

    root.mainloop()

if __name__ == "__main__":
    create_gui()
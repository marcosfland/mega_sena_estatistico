import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog
from mega_sena_app import (
    load_all_draws, get_most_frequent, get_most_frequent_period,
    get_weighted, monte_carlo_simulation, plot_frequency
)

def run_analysis(option):
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

def create_gui():
    root = tk.Tk()
    root.title("Mega-Sena Analyzer")

    tk.Label(root, text="Escolha uma análise:").pack(pady=10)

    tk.Button(root, text="Top 6 de Todos os Tempos", command=lambda: run_analysis("alltime")).pack(pady=5)
    tk.Button(root, text="Top 6 do Último Ano", command=lambda: run_analysis("lastyear")).pack(pady=5)
    tk.Button(root, text="Conjunto Estatístico Ponderado", command=lambda: run_analysis("weighted")).pack(pady=5)
    tk.Button(root, text="Visualizar Frequência", command=lambda: run_analysis("plot")).pack(pady=5)
    tk.Button(root, text="Simulação de Monte Carlo", command=lambda: run_analysis("montecarlo")).pack(pady=5)

    root.mainloop()

if __name__ == "__main__":
    create_gui()
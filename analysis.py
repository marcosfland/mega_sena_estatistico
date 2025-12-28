"""
Módulo de análise estatística para o projeto Mega-Sena Estatístico.
Inclui funções de frequência, ponderação, pares, trios, etc.
"""
# Funções como get_most_frequent, get_weighted, get_most_frequent_pairs, etc, serão movidas para cá.

import logging
import datetime
import random
from collections import Counter
from typing import List, Tuple

NUM_DEZENAS = 6
MAX_NUM_MEGA_SENA = 60
Draw = Tuple[datetime.date, Tuple[int, int, int, int, int, int]]

def get_most_frequent(draws: List[Draw], k: int = NUM_DEZENAS) -> List[int]:
    """
    Calcula os k números mais frequentes em todos os sorteios.
    """
    counter: Counter = Counter()
    for _, nums in draws:
        counter.update(nums)
    return [num for num, _ in counter.most_common(k)]

def get_most_frequent_period(draws: List[Draw], days: int = 365, k: int = NUM_DEZENAS) -> List[int]:
    """
    Calcula os k números mais frequentes em um período específico (em dias).
    """
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=days)
    filtered = [(d, nums) for d, nums in draws if d >= cutoff]
    if not filtered:
        logging.warning(f"Nenhum sorteio encontrado nos últimos {days} dias.")
        return []
    return get_most_frequent(filtered, k)

def get_weighted(draws: List[Draw], k: int = NUM_DEZENAS) -> List[int]:
    """
    Gera um conjunto de números ponderado pela frequência histórica.
    """
    counter: Counter = Counter()
    for _, nums in draws:
        counter.update(nums)
    all_nums: List[int] = list(range(1, MAX_NUM_MEGA_SENA + 1))
    weights: List[int] = [counter[n] for n in all_nums]

    if sum(weights) == 0:
        logging.warning("Não há dados de frequência para ponderar, gerando números aleatórios.")
        return sorted(random.sample(all_nums, k))

    # Normalize weights to probabilities
    total_weights: int = sum(weights)
    probs: List[float] = [w / total_weights for w in weights]

    chosen: set[int] = set()
    while len(chosen) < k:
        picks = random.choices(all_nums, weights=probs, k=k - len(chosen))
        chosen.update(picks)
    return sorted(list(chosen)) # Convert set to list and sort

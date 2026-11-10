"""Organização de bolões: participantes, cotas, jogos, custos e rateio de prêmios.

Fluxo típico::

    plan = plan_budget(spec, 200.0, 7)               # quantos jogos cabem
    bolao = create_bolao(spec, ctx, "Firma", 200.0, 7, parse_participants(texto))
    texto = share_text(spec, bolao)                  # para o WhatsApp
    resultado = check_bolao(spec, bolao, sorteio)    # depois do sorteio
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from loterias.checker import CheckResult, check_bet
from loterias.formatting import brl
from loterias.games import GameSpec
from loterias.generator import STRATEGIES, StrategyContext, generate_games
from loterias.models import Bet, Draw

MAX_PARTICIPANTS = 100
MAX_COTAS_EACH = 100


@dataclass
class Participant:
    """Integrante do bolão."""

    name: str
    cotas: int = 1
    paid: bool = False


@dataclass
class BudgetPlan:
    """Quantos jogos cabem no orçamento."""

    n_bets: int
    cost_per_bet: float
    total: float
    leftover: float


@dataclass
class Bolao:
    """Um bolão com seus jogos e participantes."""

    name: str
    game: str
    bets: list[Bet]
    participants: list[Participant]
    n_numbers: int
    strategy: str = "aleatorio"
    target_contest: Optional[int] = None
    id: Optional[int] = None

    @property
    def total_cotas(self) -> int:
        """Soma das cotas de todos os participantes."""
        return sum(p.cotas for p in self.participants)

    def total_cost(self, spec: GameSpec) -> float:
        """Custo de todos os jogos."""
        return round(sum(spec.bet_cost(len(b.numbers), len(b.trevos) or 2)
                         for b in self.bets), 2)

    def cota_value(self, spec: GameSpec) -> float:
        """Valor de uma cota, arredondado para cima no centavo."""
        if not self.total_cotas:
            return 0.0
        return math.ceil(self.total_cost(spec) / self.total_cotas * 100) / 100

    def amount_due(self, spec: GameSpec, participant: Participant) -> float:
        """Quanto um participante paga."""
        return round(self.cota_value(spec) * participant.cotas, 2)

    def to_dict(self) -> dict[str, Any]:
        """Serializa para salvar no banco."""
        data = asdict(self)
        data.pop("id")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any], bolao_id: Optional[int] = None) -> "Bolao":
        """Reconstrói um bolão salvo."""
        return cls(
            name=data["name"], game=data["game"],
            bets=[Bet(tuple(b["numbers"]), tuple(b.get("trevos", ())), b.get("extra", ""))
                  for b in data["bets"]],
            participants=[Participant(**p) for p in data["participants"]],
            n_numbers=int(data["n_numbers"]), strategy=data.get("strategy", "aleatorio"),
            target_contest=data.get("target_contest"), id=bolao_id,
        )


def plan_budget(spec: GameSpec, budget: float, n_numbers: int,
                n_trevos: int = 2) -> BudgetPlan:
    """Calcula quantos jogos de ``n_numbers`` dezenas cabem no orçamento.

    Raises:
        ValueError: Se o orçamento não pagar nem um jogo.
    """
    cost = spec.bet_cost(n_numbers, n_trevos)
    if budget < cost:
        raise ValueError(f"Orçamento insuficiente: um jogo com {n_numbers} dezenas custa "
                         f"{brl(cost)}.")
    n_bets = min(int(budget // cost + 1e-9), 500)
    total = round(n_bets * cost, 2)
    return BudgetPlan(n_bets, cost, total, round(budget - total, 2))


def parse_participants(text: str) -> list[Participant]:
    """Lê participantes, um por linha: ``"Ana, 2"``, ``"Bruno"`` (1 cota), ``"Caio; 3"``.

    Raises:
        ValueError: Linha inválida, nome repetido ou limites excedidos.
    """
    participants: list[Participant] = []
    seen: set[str] = set()
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        match = re.fullmatch(r"(.+?)(?:\s*[,;:\t]\s*|\s+)(\d+)\s*(?:cotas?)?", line)
        name, cotas = (match.group(1).strip(), int(match.group(2))) if match else (line, 1)
        if not name or len(name) > 60:
            raise ValueError(f"Linha {line_no}: nome inválido.")
        if not 1 <= cotas <= MAX_COTAS_EACH:
            raise ValueError(f"Linha {line_no}: cotas devem ficar entre 1 e {MAX_COTAS_EACH}.")
        if name.casefold() in seen:
            raise ValueError(f"Linha {line_no}: '{name}' aparece mais de uma vez.")
        seen.add(name.casefold())
        participants.append(Participant(name, cotas))
    if not participants:
        raise ValueError("Informe ao menos um participante.")
    if len(participants) > MAX_PARTICIPANTS:
        raise ValueError(f"Máximo de {MAX_PARTICIPANTS} participantes.")
    return participants


def create_bolao(spec: GameSpec, ctx: StrategyContext, name: str, budget: float,
                 n_numbers: int, participants: list[Participant],
                 strategy: str = "equilibrado", rng: Optional[random.Random] = None,
                 target_contest: Optional[int] = None) -> Bolao:
    """Monta o bolão gerando o máximo de jogos diversificados que o orçamento paga.

    Raises:
        ValueError: Nome vazio, orçamento insuficiente ou estratégia inválida.
    """
    if not name.strip():
        raise ValueError("Dê um nome ao bolão.")
    if strategy not in STRATEGIES:
        raise ValueError(f"Estratégia desconhecida: {strategy}")
    plan = plan_budget(spec, budget, n_numbers)
    bets = generate_games(spec, ctx, strategy, n_numbers, plan.n_bets, rng)
    return Bolao(name.strip(), spec.slug, bets, participants, n_numbers, strategy,
                 target_contest)


@dataclass
class BolaoCheck:
    """Resultado de um bolão num concurso."""

    contest: int
    results: list[CheckResult]
    total_prize: float
    pending: bool
    shares: dict[str, float] = field(default_factory=dict)

    @property
    def winning_bets(self) -> list[CheckResult]:
        """Somente os jogos premiados."""
        return [r for r in self.results if r.won]


def check_bolao(spec: GameSpec, bolao: Bolao, draw: Draw) -> BolaoCheck:
    """Confere todos os jogos e divide o prêmio proporcionalmente às cotas."""
    results = [check_bet(spec, bet, draw) for bet in bolao.bets]
    total = round(sum(r.total_prize for r in results), 2)
    shares = {
        p.name: math.floor(total * p.cotas / bolao.total_cotas * 100) / 100
        for p in bolao.participants
    } if bolao.total_cotas else {}
    return BolaoCheck(draw.contest, results, total, any(r.prize_pending for r in results),
                      shares)


def share_text(spec: GameSpec, bolao: Bolao) -> str:
    """Resumo do bolão pronto para colar no WhatsApp."""
    target = f" — concurso {bolao.target_contest}" if bolao.target_contest else ""
    lines = [
        f"*Bolão {bolao.name}* ({spec.name}{target})",
        f"{len(bolao.bets)} jogo(s) de {bolao.n_numbers} dezenas · "
        f"total {brl(bolao.total_cost(spec))}",
        f"{bolao.total_cotas} cota(s) de {brl(bolao.cota_value(spec))}",
        "",
        "*Participantes*",
    ]
    lines += [f"• {p.name}: {p.cotas} cota(s) = {brl(bolao.amount_due(spec, p))}"
              + (" ✅" if p.paid else "") for p in bolao.participants]
    lines += ["", "*Jogos*"]
    lines += [f"{i:02d}) {bet.as_text()}" for i, bet in enumerate(bolao.bets, start=1)]
    return "\n".join(lines)


def result_text(spec: GameSpec, bolao: Bolao, check: BolaoCheck) -> str:
    """Resumo do resultado do bolão para compartilhar."""
    lines = [f"*Bolão {bolao.name}* — resultado do concurso {check.contest} ({spec.name})"]
    winners = check.winning_bets
    if not winners:
        lines.append("Nenhum jogo premiado desta vez.")
    for res in winners:
        lines.append(f"• {res.bet.as_text()} → {res.summary()}")
    if winners:
        lines.append(f"Prêmio total: {brl(check.total_prize)}"
                     + (" (há faixas com rateio ainda não divulgado)" if check.pending else ""))
        lines += [f"  {name}: {brl(value)}" for name, value in check.shares.items()]
    return "\n".join(lines)

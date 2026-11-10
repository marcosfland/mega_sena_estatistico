"""Interface de linha de comando.

Exemplos::

    python main.py atualizar                       # todas as loterias
    python main.py gerar -j lotofacil -e equilibrado -n 16 -q 3
    python main.py estatisticas -j quina --ultimos 100
    python main.py conferir -j megasena "05 12 23 34 45 56"
    python main.py bolao -j megasena --orcamento 300 -n 7 -p "Ana:2,Bruno,Caio:3"
    python main.py backtest -j megasena --concursos 300
    python main.py agendar --hora 21:30
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional, Sequence

from loterias import bolao as bolao_mod
from loterias.alerts import check_new_results
from loterias.backtest import expected_hits, run_backtest
from loterias.checker import check_bet
from loterias.export import export_draws_csv
from loterias.formatting import brl, brl_compact, date_br, thousands
from loterias.games import GAMES, get_game
from loterias.generator import STRATEGIES, StrategyContext, generate_games, strategies_for
from loterias.models import Bet, parse_numbers
from loterias.notifier import notify
from loterias.scheduler import schedule_daily, unschedule
from loterias.services import Services, build_services
from loterias.stats import last_n, summarize

logger = logging.getLogger(__name__)


def _need_draws(services: Services, slug: str) -> list:
    """Carrega o histórico ou explica como baixá-lo."""
    draws = services.storage.load_draws(slug)
    if not draws:
        raise SystemExit(f"Base de {get_game(slug).name} vazia. Rode: python main.py atualizar "
                         f"-j {slug}")
    return draws


def cmd_atualizar(services: Services, args: argparse.Namespace) -> None:
    """Atualiza uma ou todas as loterias."""
    slugs = [get_game(args.jogo).slug] if args.jogo else list(GAMES)

    def progress(slug: str, done: int, total: int) -> None:
        print(f"\r  {get_game(slug).name}: {done}/{total}", end="", flush=True)

    results = services.updater.sync_all(slugs, progress=progress)
    for result in results:
        print("\r" + result.message() + " " * 10)
    for alert in check_new_results(services.storage, results):
        print(f"🏆 {alert.title()} {alert.message()}")
        if services.settings.notifications:
            notify(alert.title(), alert.message())


def cmd_gerar(services: Services, args: argparse.Namespace) -> None:
    """Gera jogos com uma estratégia."""
    spec = get_game(args.jogo)
    draws = _need_draws(services, spec.slug)
    ctx = StrategyContext.from_draws(spec, draws)
    n = args.dezenas or spec.bet_min
    games = generate_games(spec, ctx, args.estrategia, n, args.quantidade)
    print(f"{spec.name} · {STRATEGIES[args.estrategia].label} · {n} dezenas")
    for i, bet in enumerate(games, start=1):
        print(f"  {i:02d}) {bet.as_text(spec)}")
    print(f"Custo: {brl(spec.bet_cost(n) * len(games))}")


def cmd_estatisticas(services: Services, args: argparse.Namespace) -> None:
    """Mostra o resumo estatístico."""
    spec = get_game(args.jogo)
    draws = last_n(_need_draws(services, spec.slug), args.ultimos)
    s = summarize(spec, draws)
    fmt = spec.format_number
    print(f"{spec.name}: {thousands(s.contests)} concursos analisados")
    print("Mais sorteadas:  " + "  ".join(f"{fmt(n)}({s.freq[n]})" for n in s.hot))
    print("Menos sorteadas: " + "  ".join(f"{fmt(n)}({s.freq[n]})" for n in s.cold))
    print("Mais atrasadas:  " + "  ".join(f"{fmt(n)}({s.delay[n]})" for n in s.overdue))
    print(f"Frequência esperada por dezena: {s.expected:.1f}")
    print(f"Qui-quadrado: {s.chi.statistic:.1f} (p = {s.chi.p_value:.3f}) — {s.chi.verdict()}")
    print(f"Soma média: {s.sum_mean:.0f} (80% entre {s.sum_band[0]:.0f} e {s.sum_band[1]:.0f})")


def cmd_conferir(services: Services, args: argparse.Namespace) -> None:
    """Confere uma aposta."""
    spec = get_game(args.jogo)
    bet = Bet(spec.validate_numbers(spec.parse_input(args.numeros)),
              spec.validate_trevos(parse_numbers(args.trevos or "")))
    storage = services.storage
    draw = storage.get_draw(spec.slug, args.concurso) if args.concurso \
        else storage.latest_draw(spec.slug)
    if draw is None:
        raise SystemExit("Concurso não encontrado na base. Atualize primeiro.")
    result = check_bet(spec, bet, draw)
    print(f"Concurso {draw.contest} ({date_br(draw.date)}): "
          + " | ".join(spec.format_bet(s) for s in draw.number_sets()))
    print(result.summary())
    if result.won:
        print("Prêmio: valor do rateio não disponível para este concurso"
              if result.prize_pending and not result.total_prize
              else f"Prêmio: {brl(result.total_prize)}")


def cmd_bolao(services: Services, args: argparse.Namespace) -> None:
    """Monta um bolão e imprime o texto para compartilhar."""
    spec = get_game(args.jogo)
    draws = _need_draws(services, spec.slug)
    participants = bolao_mod.parse_participants(args.participantes.replace(",", "\n")
                                                .replace(":", ","))
    latest = draws[-1].contest
    bolao = bolao_mod.create_bolao(
        spec, StrategyContext.from_draws(spec, draws), args.nome, args.orcamento,
        args.dezenas or spec.bet_min, participants, args.estrategia, target_contest=latest + 1)
    print(bolao_mod.share_text(spec, bolao))
    if args.salvar:
        bolao.id = services.storage.save_bolao(spec.slug, bolao.name, bolao.to_dict())
        print(f"\nBolão salvo (id {bolao.id}).")


def cmd_backtest(services: Services, args: argparse.Namespace) -> None:
    """Compara estratégias nos concursos passados."""
    spec = get_game(args.jogo)
    draws = _need_draws(services, spec.slug)
    n = args.dezenas or spec.bet_min
    results = run_backtest(spec, draws, [s.key for s in strategies_for(spec)],
                           args.concursos, n, seed=args.semente)
    print(f"{spec.name}: {args.concursos} concursos, {n} dezenas por jogo. "
          f"Média teórica do acaso: {expected_hits(spec, n):.3f} acertos")
    for r in results:
        print(f"  {r.label:<20} média {r.mean_hits:.3f} · premiado em {r.wins} · "
              f"gasto {brl(r.spent)} · retorno {brl(r.won)}")


def cmd_exportar(services: Services, args: argparse.Namespace) -> None:
    """Exporta o histórico para CSV."""
    spec = get_game(args.jogo)
    path = export_draws_csv(spec, _need_draws(services, spec.slug), args.arquivo)
    print(f"Arquivo gerado: {path}")


def cmd_jogos(services: Services, args: argparse.Namespace) -> None:
    """Lista as loterias e o estado de cada base."""
    for spec in GAMES.values():
        latest = services.storage.latest_draw(spec.slug)
        status = (f"concurso {latest.contest} ({date_br(latest.date)}), próximo "
                  f"{brl_compact(latest.next_estimate)}") if latest else "base vazia"
        print(f"  {spec.slug:<15} {spec.name:<13} {brl(spec.price):>9}  {status}")


def cmd_agendar(services: Services, args: argparse.Namespace) -> None:
    """Agenda ou remove a atualização diária."""
    ok, message = unschedule() if args.remover else schedule_daily(args.hora)
    print(message)
    if not ok:
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    """Monta o parser com todos os subcomandos."""
    parser = argparse.ArgumentParser(prog="main.py", description="Loterias Estatístico")
    sub = parser.add_subparsers(dest="cmd", required=True)
    jogo = argparse.ArgumentParser(add_help=False)
    jogo.add_argument("-j", "--jogo", default="megasena", choices=list(GAMES))

    p = sub.add_parser("atualizar", help="baixa concursos novos")
    p.add_argument("-j", "--jogo", choices=list(GAMES), help="padrão: todas")
    p.set_defaults(func=cmd_atualizar)
    p = sub.add_parser("gerar", parents=[jogo], help="gera jogos")
    p.add_argument("-e", "--estrategia", default="mais_sorteados", choices=list(STRATEGIES))
    p.add_argument("-n", "--dezenas", type=int)
    p.add_argument("-q", "--quantidade", type=int, default=1)
    p.set_defaults(func=cmd_gerar)
    p = sub.add_parser("estatisticas", parents=[jogo], help="resumo estatístico")
    p.add_argument("--ultimos", type=int, help="usar só os N concursos mais recentes")
    p.set_defaults(func=cmd_estatisticas)
    p = sub.add_parser("conferir", parents=[jogo], help="confere uma aposta")
    p.add_argument("numeros", help='dezenas, ex.: "05 12 23 34 45 56" '
                   '(Super Sete, por coluna: "5 3/8 7 1 4 0 6")')
    p.add_argument("-c", "--concurso", type=int)
    p.add_argument("-t", "--trevos", help="+Milionária, ex.: \"1 4\"")
    p.set_defaults(func=cmd_conferir)
    p = sub.add_parser("bolao", parents=[jogo], help="monta um bolão")
    p.add_argument("--nome", default="dos Amigos")
    p.add_argument("--orcamento", type=float, required=True)
    p.add_argument("-n", "--dezenas", type=int)
    p.add_argument("-e", "--estrategia", default="equilibrado", choices=list(STRATEGIES))
    p.add_argument("-p", "--participantes", required=True, help='"Ana:2,Bruno,Caio:3"')
    p.add_argument("--salvar", action="store_true")
    p.set_defaults(func=cmd_bolao)
    p = sub.add_parser("backtest", parents=[jogo], help="compara estratégias")
    p.add_argument("--concursos", type=int, default=200)
    p.add_argument("-n", "--dezenas", type=int)
    p.add_argument("--semente", type=int)
    p.set_defaults(func=cmd_backtest)
    p = sub.add_parser("exportar", parents=[jogo], help="exporta histórico CSV")
    p.add_argument("arquivo")
    p.set_defaults(func=cmd_exportar)
    p = sub.add_parser("jogos", help="lista loterias e bases")
    p.set_defaults(func=cmd_jogos)
    p = sub.add_parser("agendar", help="agenda atualização diária")
    p.add_argument("--hora", default="21:30")
    p.add_argument("--remover", action="store_true")
    p.set_defaults(func=cmd_agendar)
    return parser


def main(argv: Optional[Sequence[str]] = None, services: Optional[Services] = None) -> int:
    """Executa a CLI e devolve o código de saída."""
    args = build_parser().parse_args(argv)
    own = services is None
    services = services or build_services()
    try:
        args.func(services, args)
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    finally:
        if own:
            services.close()
    return 0

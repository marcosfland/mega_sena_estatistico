"""Atualiza a base versionada ``dados/<loteria>.jsonl`` (rotina do GitHub Actions).

Fluxo: importa os arquivos atuais numa base temporária, baixa só os concursos
novos (API oficial da Caixa, com a comunitária de reserva) e regrava os
arquivos que mudaram. A própria base do repositório não é usada como fonte.

Uso::

    python scripts/atualizar_base.py [--dados dados]

Saídas para o GitHub Actions (quando as variáveis existem):

* ``GITHUB_OUTPUT``: ``alterou=true|false`` e ``mensagem=<resumo do commit>``;
* ``GITHUB_STEP_SUMMARY``: tabela com o resultado de cada loteria.

Código de saída 1 só quando *todas* as loterias falharem (a execução fica
vermelha e o GitHub avisa por e-mail).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loterias.api_client import LotteryApiClient  # noqa: E402
from loterias.dump import export_storage, seed_storage  # noqa: E402
from loterias.games import get_game  # noqa: E402
from loterias.storage import Storage  # noqa: E402
from loterias.updater import SyncResult, Updater  # noqa: E402


def commit_message(results: list[SyncResult]) -> str:
    """Resumo curto para o commit, ex.: ``Mega-Sena 3072, Quina 6890``."""
    parts = [f"{get_game(r.game).name} {r.latest_contest}" for r in results if r.ok and r.added]
    return "Atualiza base de dados: " + (", ".join(parts) if parts else "sem concursos novos")


def summary_table(results: list[SyncResult], changed: list[str]) -> str:
    """Tabela Markdown para o resumo da execução."""
    lines = ["| Loteria | Último concurso | Novos | Situação |", "|---|---|---|---|"]
    for r in results:
        status = f"⚠️ {r.error}" if not r.ok else ("✅ atualizada" if r.game in changed
                                                    else "sem novidades")
        lines.append(f"| {get_game(r.game).name} | {r.latest_contest or '—'} | {r.added} | "
                     f"{status} |")
    return "\n".join(lines) + "\n"


def write_github_outputs(results: list[SyncResult], changed: list[str]) -> None:
    """Escreve as saídas e o resumo do GitHub Actions, se estiver rodando lá."""
    output = os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"alterou={'true' if changed else 'false'}\n")
            fh.write(f"mensagem={commit_message(results)}\n")
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## Atualização da base de dados\n\n" + summary_table(results, changed))


def update(dados: Path) -> tuple[list[SyncResult], list[str]]:
    """Executa a atualização e devolve ``(resultados, loterias alteradas)``."""
    with tempfile.TemporaryDirectory() as tmp:
        storage = Storage(Path(tmp) / "base.db")
        seed_storage(storage, dados, only_empty=False)
        with LotteryApiClient(dumps_url=None) as client:
            results = Updater(storage, client, request_delay=0.2).sync_all()
        changed = export_storage(storage, dados)
    return results, changed


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada; devolve o código de saída."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Atualiza dados/*.jsonl")
    parser.add_argument("--dados", type=Path,
                        default=Path(__file__).resolve().parent.parent / "dados")
    args = parser.parse_args(argv)
    results, changed = update(args.dados)
    for r in results:
        print(r.message())
    print(commit_message(results))
    write_github_outputs(results, changed)
    return 1 if results and all(not r.ok for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())

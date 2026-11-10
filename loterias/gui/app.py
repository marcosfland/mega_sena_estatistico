"""Janela principal e controlador da interface gráfica."""

from __future__ import annotations

import logging
from typing import Callable, Optional

import customtkinter as ctk

from loterias.alerts import PrizeAlert, check_new_results
from loterias.formatting import brl
from loterias.games import DEFAULT_GAME, GAMES, GameSpec, get_game
from loterias.gui import theme as t
from loterias.gui.page_backtest import BacktestPage
from loterias.gui.page_base import Page
from loterias.gui.page_bolao import BolaoPage
from loterias.gui.page_checker import CheckerPage
from loterias.gui.page_generator import GeneratorPage
from loterias.gui.page_stats import StatsPage
from loterias.gui.runner import TaskRunner
from loterias.gui.sidebar import Sidebar
from loterias.gui.toast import Toast
from loterias.gui.widgets import label
from loterias.models import Draw
from loterias.notifier import notify
from loterias.services import Services, build_services
from loterias.updater import SyncResult

logger = logging.getLogger(__name__)

PAGES: tuple[type[Page], ...] = (GeneratorPage, StatsPage, CheckerPage, BolaoPage, BacktestPage)


class App(ctk.CTk):
    """Aplicativo Loterias Estatístico.

    Args:
        services: Serviços já montados (útil em testes); padrão: :func:`build_services`.
    """

    def __init__(self, services: Optional[Services] = None) -> None:
        self.services = services or build_services()
        ctk.set_appearance_mode(self.services.settings.appearance)
        super().__init__(fg_color=t.BG)
        self.title("Loterias Estatístico")
        self.geometry("1240x800")
        self.minsize(1000, 660)
        self.runner = TaskRunner(self)
        self._syncing = False
        self._auto_job: Optional[str] = None
        slug = self.services.settings.last_game
        self.spec: GameSpec = GAMES.get(slug) or GAMES[DEFAULT_GAME]

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = Sidebar(self, self, self.set_game)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self._build_main()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.set_game(self.spec.slug)
        self.schedule_auto_sync(initial=True)

    # ----------------------------------------------------------------- layout
    def _build_main(self) -> None:
        """Cabeçalho, navegação e área das páginas."""
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=t.PAD, pady=(20, t.PAD))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.grid_columnconfigure(0, weight=1)
        self.title_label = label(header, "", 26, "bold")
        self.title_label.grid(row=0, column=0, sticky="w")
        self.subtitle_label = label(header, "", 13, color=t.MUTED, height=18)
        self.subtitle_label.grid(row=1, column=0, columnspan=2, sticky="w")
        self.nav = ctk.CTkSegmentedButton(
            header, values=[p.title for p in PAGES], command=self.show_page, height=34,
            font=t.font(13), corner_radius=t.RADIUS_SM, fg_color=t.SURFACE_ALT,
            unselected_color=t.SURFACE_ALT, unselected_hover_color=t.BORDER,
            text_color=t.TEXT)
        self.nav.grid(row=0, column=1, sticky="e")
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        self.pages: dict[str, Page] = {}
        for cls in PAGES:
            page = cls(content, self)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[cls.title] = page
        self.nav.set(PAGES[0].title)
        self.show_page(PAGES[0].title)

    def show_page(self, title: str) -> None:
        """Traz uma página para a frente."""
        page = self.pages[title]
        page.tkraise()
        page.on_show()

    # ------------------------------------------------------------------ dados
    def draws(self, slug: Optional[str] = None) -> list[Draw]:
        """Histórico (com cache) da loteria ativa ou de outra."""
        return self.services.storage.load_draws(slug or self.spec.slug)

    def set_game(self, slug: str) -> None:
        """Troca a loteria ativa e atualiza toda a interface."""
        self.spec = get_game(slug)
        settings = self.services.settings
        if settings.last_game != slug:
            settings.last_game = slug
            settings.save()
        spec = self.spec
        bet = (f"{spec.bet_min}" if spec.bet_min == spec.bet_max
               else f"{spec.bet_min} a {spec.bet_max}")
        self.title_label.configure(text=spec.name, text_color=t.accent(spec.color))
        if spec.is_columns:
            drawn = f"1 dígito (0 a 9) sorteado em cada uma das {spec.columns} colunas"
        else:
            drawn = (f"{spec.draw_size} dezenas sorteadas de "
                     f"{spec.format_number(spec.min_number)} a "
                     f"{spec.format_number(spec.max_number)}")
        self.subtitle_label.configure(
            text=f"{drawn} · aposte {bet} · a partir de {brl(spec.price)}")
        self.nav.configure(selected_color=t.accent_soft(spec.color),
                           selected_hover_color=t.accent_soft(spec.color),
                           text_color=t.TEXT)
        self.sidebar.select(spec)
        self.refresh_base_status()
        for page in self.pages.values():
            page.on_game_changed()

    def refresh_base_status(self) -> None:
        """Atualiza o cartão da base na barra lateral."""
        storage = self.services.storage
        self.sidebar.show_base(self.spec, storage.latest_draw(self.spec.slug),
                               storage.count_draws(self.spec.slug))

    # ---------------------------------------------------------- sincronização
    def start_sync(self, slugs: Optional[list[str]]) -> None:
        """Baixa concursos novos em segundo plano (uma sincronização por vez)."""
        if self._syncing:
            return
        self._syncing = True
        names = "todas as loterias" if slugs is None else get_game(slugs[0]).name
        self.sidebar.set_busy(True, f"Verificando {names}…")

        def work(progress: Callable[..., None]) -> list[SyncResult]:
            results = []
            for slug in slugs or list(GAMES):
                result = self.services.updater.sync_game(slug, progress=progress)
                alerts = check_new_results(self.services.storage, [result])
                progress(result, alerts)  # avisa a interface assim que cada loteria termina
                results.append(result)
            return results

        def on_progress(*args: object) -> None:
            if isinstance(args[0], SyncResult):
                self._game_synced(args[0], args[1])  # type: ignore[arg-type]
                return
            slug, done, total = args
            self.sidebar.set_progress(done / total if total else 0,
                                      f"{get_game(str(slug)).name}: {done} de {total}")

        self.runner.submit(work, with_progress=True, on_progress=on_progress,
                           on_success=self._sync_finished, on_error=self._sync_failed,
                           on_done=self._sync_done)

    def _game_synced(self, result: SyncResult, alerts: list[PrizeAlert]) -> None:
        """Uma loteria terminou: avisa prêmios e atualiza a tela se for a ativa."""
        for alert in alerts:
            Toast(self, alert.title(), alert.message(), get_game(alert.game).color,
                  duration_ms=0)
            if self.services.settings.notifications:
                self.runner.submit(notify, alert.title(), alert.message())
        if result.game == self.spec.slug and result.added:
            self.refresh_base_status()
            for page in self.pages.values():
                page.on_data_changed()

    def _sync_finished(self, results: list[SyncResult]) -> None:
        """Mostra o resumo final da sincronização."""
        errors = [r for r in results if not r.ok]
        added = sum(r.added for r in results)
        if errors and len(errors) == len(results):
            self.sidebar.set_sync_message(errors[0].error, error=True)
        elif errors:
            self.sidebar.set_sync_message(
                f"{added} concurso(s) novo(s); falhou: "
                + ", ".join(get_game(r.game).name for r in errors), error=True)
        else:
            self.sidebar.set_sync_message(
                f"{added} concurso(s) novo(s)" if added else "Tudo atualizado")
        self.refresh_base_status()

    def _sync_failed(self, exc: BaseException) -> None:
        """Erro inesperado na sincronização."""
        self.sidebar.set_sync_message(f"Erro ao atualizar: {exc}", error=True)

    def _sync_done(self) -> None:
        """Libera os botões de atualização."""
        self._syncing = False
        self.sidebar.set_busy(False, self.sidebar.sync_label.cget("text"))

    def schedule_auto_sync(self, initial: bool = False) -> None:
        """(Re)agenda a atualização automática conforme as preferências."""
        if self._auto_job is not None:
            self.after_cancel(self._auto_job)
            self._auto_job = None
        settings = self.services.settings
        if not settings.auto_update:
            return
        delay_ms = 1200 if initial else settings.update_interval_min * 60_000

        def tick() -> None:
            self._auto_job = None
            self.start_sync(None)
            self.schedule_auto_sync()

        self._auto_job = self.after(delay_ms, tick)

    # ------------------------------------------------------------- aparência
    def set_appearance(self, mode: str) -> None:
        """Troca entre claro, escuro e sistema."""
        ctk.set_appearance_mode(mode)
        self.services.settings.appearance = mode
        self.services.settings.save()
        self.after(50, lambda: [p.on_appearance_changed() for p in self.pages.values()])

    def close(self) -> None:
        """Encerra threads de interface, conexões e a janela."""
        if self._auto_job is not None:
            self.after_cancel(self._auto_job)
        self.runner.close()
        for page in self.pages.values():
            page.destroy()
        self.services.close()
        self.quit()
        self.destroy()


def launch() -> None:
    """Abre a interface gráfica."""
    app = App()
    app.mainloop()

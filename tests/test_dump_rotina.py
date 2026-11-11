"""Base versionada (dados/*.jsonl), fonte "repositório" do cliente e rotina de atualização."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import requests
from conftest import FakeSource, make_draws

from loterias import dump
from loterias.api_client import ApiError, LotteryApiClient
from loterias.games import GAMES, GameSpec, get_game
from loterias.storage import Storage

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import atualizar_base  # noqa: E402


@pytest.mark.parametrize("slug", list(GAMES))
def test_roundtrip_every_game(slug: str) -> None:
    """Todos os campos sobrevivem a dumps/loads, em todas as loterias."""
    spec = get_game(slug)
    draws = make_draws(spec, 5)
    text = dump.dumps(reversed(draws))
    assert text.count("\n") == 5 and text.startswith('{"c":1,')  # ordenado
    assert dump.loads(spec, text) == draws


def test_loads_skips_bad_lines(mega: GameSpec) -> None:
    """Linhas corrompidas não derrubam a leitura."""
    good = dump.dumps(make_draws(mega, 2))
    assert len(dump.loads(mega, good + "lixo\n{}\n\n")) == 2


def test_export_and_seed(tmp_path: Path, storage: Storage) -> None:
    """Exporta só o que mudou; importa para bases vazias (ou todas, se pedido)."""
    mega, quina = get_game("megasena"), get_game("quina")
    storage.upsert_draws(make_draws(mega, 10) + make_draws(quina, 4))
    folder = tmp_path / "dados"
    assert sorted(dump.export_storage(storage, folder)) == ["megasena", "quina"]
    assert dump.export_storage(storage, folder) == []  # idêntico: não reescreve
    other = Storage(tmp_path / "outra.db")
    assert dump.seed_storage(other, folder) == {"megasena": 10, "quina": 4}
    assert dump.seed_storage(other, folder) == {}  # já preenchida
    assert dump.seed_storage(other, folder, only_empty=False) == {"megasena": 10, "quina": 4}
    assert dump.seed_storage(other, tmp_path / "inexistente") == {}


class _Resp:
    """Resposta HTTP mínima."""

    def __init__(self, status: int, body: Any) -> None:
        self.status_code, self.body = status, body
        self.text = body if isinstance(body, str) else ""

    def raise_for_status(self) -> None:
        """Simula requests."""
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self) -> Any:
        """Corpo JSON."""
        return self.body


class _Session(requests.Session):
    """Só a base do repositório responde; as APIs estão fora do ar."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text, self.urls = text, []

    def get(self, url: str, **_kw: Any) -> _Resp:  # type: ignore[override]
        """Responde apenas ao arquivo JSONL."""
        self.urls.append(url)
        if url.endswith("/dados/megasena.jsonl"):
            return _Resp(200, self.text)
        raise requests.ConnectionError("fora do ar")


def test_client_uses_repository_base(mega: GameSpec) -> None:
    """Histórico completo vem do repositório; o último concurso cai nele se as APIs falham."""
    draws = make_draws(mega, 30)
    session = _Session(dump.dumps(draws))
    client = LotteryApiClient(retries=0, session=session, dumps_url="https://x/dados/")
    assert client.fetch_all(mega) == draws
    assert client.fetch_latest(mega).contest == 30
    assert client.fetch_contest(mega, 7) == draws[6]
    downloads = [u for u in session.urls if u.endswith(".jsonl")]
    assert len(downloads) == 1  # cache de 10 minutos
    with pytest.raises(ApiError, match="repositório"):
        client.fetch_contest(mega, 99)
    disabled = LotteryApiClient(retries=0, session=_Session(""), dumps_url=None)
    with pytest.raises(ApiError):
        disabled.fetch_dump(mega)


def test_routine_updates_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A rotina importa a base, baixa o que falta, regrava e informa o GitHub Actions."""
    mega = get_game("megasena")
    history = make_draws(mega, 60)
    folder = tmp_path / "dados"
    folder.mkdir()
    dump.dump_path(folder, mega).write_text(dump.dumps(history[:50]), encoding="utf-8")
    source = FakeSource({"megasena": history})

    class _Client:
        """Substitui o cliente HTTP pela fonte falsa."""

        def __init__(self, **_kw: Any) -> None:
            pass

        def __enter__(self) -> FakeSource:
            return source

        def __exit__(self, *_exc: object) -> None:
            return None

    monkeypatch.setattr(atualizar_base, "LotteryApiClient", _Client)
    output, summary = tmp_path / "out.txt", tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert atualizar_base.main(["--dados", str(folder)]) == 0
    assert len(dump.loads(mega, dump.dump_path(folder, mega).read_text("utf-8"))) == 60
    text = output.read_text(encoding="utf-8")
    assert "alterou=true" in text and "Mega-Sena 60" in text
    assert "| Mega-Sena | 60 | 10 | ✅ atualizada |" in summary.read_text(encoding="utf-8")
    assert not dump.dump_path(folder, get_game("quina")).exists()  # falhou: nada gravado


def test_routine_fails_when_every_game_fails(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    """Se nenhuma loteria atualizar, o código de saída é 1 (execução vermelha)."""
    offline = FakeSource({}, fail_latest=True)

    class _Client:
        """Cliente sempre offline."""

        def __init__(self, **_kw: Any) -> None:
            pass

        def __enter__(self) -> FakeSource:
            return offline

        def __exit__(self, *_exc: object) -> None:
            return None

    monkeypatch.setattr(atualizar_base, "LotteryApiClient", _Client)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert atualizar_base.main(["--dados", str(tmp_path / "dados")]) == 1

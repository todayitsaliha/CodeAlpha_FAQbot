"""Tests for the server entry point."""

import run
from app.factory import StartupError


class FakeApp:
    def __init__(self):
        self.started = None

    def run(self, host, port, debug):
        self.started = (host, port, debug)


def test_startup_problem_exits_with_a_clear_message(monkeypatch, capsys):
    def refuse(**_kwargs):
        raise StartupError("FAQ file not found")

    monkeypatch.setattr(run, "create_app", refuse)
    assert run.main([]) == 1
    assert "Cannot start the FAQ chatbot: FAQ file not found" in capsys.readouterr().err


def test_dev_mode_uses_the_flask_server_with_debug_off(monkeypatch):
    app = FakeApp()
    monkeypatch.setattr(run, "create_app", lambda **_kwargs: app)
    assert run.main(["--dev", "--host", "0.0.0.0", "--port", "8123"]) == 0
    assert app.started == ("0.0.0.0", 8123, False)


def test_environment_variables_set_host_and_port(monkeypatch):
    app = FakeApp()
    monkeypatch.setattr(run, "create_app", lambda **_kwargs: app)
    monkeypatch.setenv("FAQBOT_HOST", "10.0.0.5")
    monkeypatch.setenv("FAQBOT_PORT", "9001")
    run.main(["--dev"])
    assert app.started == ("10.0.0.5", 9001, False)


def test_production_mode_uses_waitress(monkeypatch):
    calls = {}
    monkeypatch.setattr(run, "create_app", lambda **_kwargs: "APP")
    monkeypatch.setattr(
        "waitress.serve", lambda app, host, port: calls.update(a=app, h=host, p=port)
    )
    assert run.main(["--port", "8001"]) == 0
    assert calls == {"a": "APP", "h": "127.0.0.1", "p": 8001}

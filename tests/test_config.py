from __future__ import annotations

from pathlib import Path

import pytest

from padel_bot.config import cargar_config

RAIZ = Path(__file__).parent.parent


def test_config_del_repo_es_valida(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    config = cargar_config(RAIZ / "config.yaml")
    assert config.notificaciones.telegram_chat_id == "12345"
    assert "pala" in config.filtros.categorias
    assert config.tienda("padelnuestro") is not None
    assert all(not t.url_base.endswith("/") for t in config.tiendas)


def test_variable_ausente_queda_en_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert cargar_config(RAIZ / "config.yaml").notificaciones.telegram_chat_id is None

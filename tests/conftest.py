"""Shared pytest fixtures for the cosquin-tales skill test suite."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_INIT_PATH = Path(__file__).resolve().parents[1] / "__init__.py"
_spec = importlib.util.spec_from_file_location("cosquin_tales_skill", _INIT_PATH)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

CosquinTales = _module.CosquinTales
StoryFetchError = _module.StoryFetchError
COMMON_READING_SEARCH_RESPONSE = _module.COMMON_READING_SEARCH_RESPONSE
COMMON_READING_FETCH_CONTENT_RESPONSE = _module.COMMON_READING_FETCH_CONTENT_RESPONSE
COMMON_READING_PONG = _module.COMMON_READING_PONG


@pytest.fixture
def skill(monkeypatch):
    s = CosquinTales.__new__(CosquinTales)
    s.log = MagicMock()
    s.skill_id = "ovos-skill-cosquin-tales.test"
    s.status = MagicMock()
    s._bus = MagicMock()
    s._settings = {}
    monkeypatch.setattr(CosquinTales, "lang", "fr-fr", raising=False)
    s._book_soup_cache = {}
    s.index = {}
    return s

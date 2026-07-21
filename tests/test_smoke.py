"""Smoke tests + the load-time language gate in initialize()."""
from unittest.mock import MagicMock

from conftest import CosquinTales, StoryFetchError


def test_imports_cleanly():
    assert CosquinTales is not None
    assert issubclass(StoryFetchError, Exception)


def test_is_an_ovos_skill():
    from ovos_workshop.skills import OVOSSkill
    assert issubclass(CosquinTales, OVOSSkill)


def test_load_index_uses_bundled_fr_fr(skill):
    index = skill._load_index()
    assert len(index) > 25
    assert "JEAN DE L'OURS" in index


def test_initialize_stays_inert_for_non_french_device(skill, monkeypatch):
    monkeypatch.setattr(CosquinTales, "lang", "en-us", raising=False)
    skill._load_index = MagicMock()
    skill.add_event = MagicMock()

    skill.initialize()

    skill._load_index.assert_not_called()
    skill.add_event.assert_not_called()
    assert skill.index == {}


def test_initialize_loads_normally_for_french_device(skill, monkeypatch):
    monkeypatch.setattr(CosquinTales, "lang", "fr-fr", raising=False)
    skill._load_index = MagicMock(return_value={"JEAN DE L'OURS": {}})
    skill.add_event = MagicMock()

    skill.initialize()

    skill._load_index.assert_called_once()
    assert skill.add_event.call_count == 2
    assert skill.index == {"JEAN DE L'OURS": {}}

"""Smoke tests + loading on every device language."""
from unittest.mock import MagicMock

import pytest

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


@pytest.mark.parametrize("lang", ["fr-fr", "en-us", "de-de", "da-dk"])
def test_initialize_loads_on_any_device_language(skill, monkeypatch, lang):
    """A HiveMind hub runs one ovos-core for users in several languages,
    so the device's own language cannot decide whether this provider is
    there at all - it always loads, and each search's language decides
    whether it answers (see test_request_language.py)."""
    monkeypatch.setattr(CosquinTales, "lang", lang, raising=False)
    skill._load_index = MagicMock(return_value={"JEAN DE L'OURS": {}})
    skill.add_event = MagicMock()

    skill.initialize()

    skill._load_index.assert_called_once()
    assert skill.add_event.call_count == 3
    assert skill.index == {"JEAN DE L'OURS": {}}
    logged = " ".join(str(c) for c in skill.log.info.call_args_list)
    assert "French" in logged and "fr-*" in logged

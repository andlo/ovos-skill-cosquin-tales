"""Whether this provider loads at all is decided by the languages the
installation is configured for - the device's 'lang' plus 'secondary_langs'
in mycroft.conf - not by the device language alone: a HiveMind hub lists
the languages its users speak in secondary_langs."""
from unittest.mock import MagicMock

import pytest

from conftest import CosquinTales


def _initialize(skill, monkeypatch, native_langs):
    monkeypatch.setattr(CosquinTales, "native_langs", native_langs, raising=False)
    skill._load_index = MagicMock(return_value={"A STORY": {}})
    skill.add_event = MagicMock()
    skill.initialize()
    return skill


@pytest.mark.parametrize("native_langs", [
    ["fr-XX".replace("XX", "fr".upper())],
    ["en-US", "fr-XX".replace("XX", "fr".upper())] if "fr" != "en" else ["da-DK", "en-GB"],
    ["da-DK", "fr"],
])
def test_loads_when_fr_is_configured(skill, monkeypatch, native_langs):
    _initialize(skill, monkeypatch, native_langs)
    skill._load_index.assert_called_once()
    assert skill.add_event.call_count == 4  # search, fetch, ping, vocabulary.get
    assert skill.served == {"fr"}


@pytest.mark.parametrize("native_langs", [
    ["xx-XX"], ["pt-PT", "xx-XX"], [],
])
def test_stays_inert_when_fr_is_not_configured(skill, monkeypatch, native_langs):
    _initialize(skill, monkeypatch, native_langs)
    skill._load_index.assert_not_called()
    skill.add_event.assert_not_called()
    assert skill.index == {}
    assert "secondary_langs" in " ".join(str(c) for c in skill.log.info.call_args_list)

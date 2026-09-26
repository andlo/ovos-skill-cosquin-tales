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

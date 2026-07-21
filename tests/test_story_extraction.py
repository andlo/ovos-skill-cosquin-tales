"""Tests for get_story_paragraphs() - includes a regression case for the
key structural decision found while building this: each story's
paragraphs must stop at the 'REMARQUES' (<h3>) scholarly commentary
that follows every tale, not just at the next story's <h2>."""
from unittest.mock import MagicMock

import pytest
import requests
from conftest import StoryFetchError

SAMPLE_HTML = """
<html><body>
<h2 id="I"><a id="Page_1"></a>I<br/>
JEAN DE L'OURS</h2>
<p>Il était une fois un bûcheron.</p>
<p>Il devint fort et brave.</p>
<h3>REMARQUES</h3>
<p>Ce conte se retrouve dans plusieurs provinces de France.</p>
<h2 id="II"><a id="Page_28"></a>II<br/>
LA BICHE BLANCHE</h2>
<p>Il y avait une princesse changée en biche.</p>
</body></html>
"""


def test_get_story_paragraphs_stops_before_remarques(skill, monkeypatch):
    fake_response = MagicMock(text=SAMPLE_HTML)
    fake_response.raise_for_status = MagicMock()
    monkeypatch.setattr(requests, "get", lambda *a, **kw: fake_response)

    paragraphs = skill.get_story_paragraphs({"url": "http://x/book", "anchor": "I"})

    assert paragraphs == ["Il était une fois un bûcheron.", "Il devint fort et brave."]
    assert "plusieurs provinces" not in " ".join(paragraphs)


def test_get_story_paragraphs_second_story(skill, monkeypatch):
    fake_response = MagicMock(text=SAMPLE_HTML)
    fake_response.raise_for_status = MagicMock()
    monkeypatch.setattr(requests, "get", lambda *a, **kw: fake_response)

    paragraphs = skill.get_story_paragraphs({"url": "http://x/book", "anchor": "II"})

    assert paragraphs == ["Il y avait une princesse changée en biche."]


def test_get_story_paragraphs_missing_anchor_raises(skill, monkeypatch):
    fake_response = MagicMock(text=SAMPLE_HTML)
    fake_response.raise_for_status = MagicMock()
    monkeypatch.setattr(requests, "get", lambda *a, **kw: fake_response)

    with pytest.raises(StoryFetchError):
        skill.get_story_paragraphs({"url": "http://x/book", "anchor": "XCIX"})


def test_get_book_soup_caches_and_wraps_request_exception(skill, monkeypatch):
    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return MagicMock(text=SAMPLE_HTML, raise_for_status=MagicMock())

    monkeypatch.setattr(requests, "get", fake_get)
    skill._get_book_soup("http://x/book")
    skill._get_book_soup("http://x/book")
    assert len(calls) == 1

    def fail(*a, **kw):
        raise requests.ConnectionError("boom")
    monkeypatch.setattr(requests, "get", fail)
    with pytest.raises(StoryFetchError):
        skill._get_book_soup("http://x/other-book")

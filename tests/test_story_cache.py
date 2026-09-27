"""Fetching a story: one request per book, the extracted text cached on
disk, a descriptive User-Agent, revalidation with If-Modified-Since, and
backing off when Project Gutenberg does not answer. No network: every
request is answered by FakeGutenberg (see conftest.py)."""
import gc
import json
import os
import threading
import time

import pytest
import requests
from bs4 import BeautifulSoup
from ovos_config.locations import get_xdg_cache_save_path

from conftest import StoryFetchError, fixture_page, response, skill_module
from test_bus_protocol import make_message

URL = "https://www.gutenberg.org/cache/epub/57892/pg57892-images.html"
LAST_MODIFIED = "Sat, 04 Mar 2023 15:20:10 GMT"
INDEX = {
    "JEAN DE L'OURS": {"url": URL, "anchor": "I"},
    "PEUIL & PUNCE": {"url": URL, "anchor": "XVIII"},
    "LA BICHE BLANCHE": {"url": URL, "anchor": "XXI"},
    "LA POUILLOTTE & LE COUCHERILLOT": {"url": URL, "anchor": "XXIX"},
    # not in the cut-down page
    "LE FOLLET": {"url": URL, "anchor": "VI"},
}
BICHE = INDEX["LA BICHE BLANCHE"]
JEAN = INDEX["JEAN DE L'OURS"]
FOLLET = INDEX["LE FOLLET"]


def book(last_modified=LAST_MODIFIED):
    return response(fixture_page("contes-de-lorraine.html"), last_modified=last_modified)


@pytest.fixture
def lorraine(skill, gutenberg):
    skill.index = dict(INDEX)
    gutenberg.pages[URL] = book()
    return skill


def cache_files(skill):
    return sorted(os.listdir(skill._story_cache.directory))


def age_cache(skill, seconds):
    for name in cache_files(skill):
        path = os.path.join(skill._story_cache.directory, name)
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
        record["fetched_at"] -= seconds
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f)


def end_backoff(skill):
    for key, (when, what) in list(skill._failures.items()):
        skill._failures[key] = (when - skill_module.FAILURE_BACKOFF - 1, what)


def test_a_book_is_fetched_once_for_all_its_stories(lorraine, gutenberg):
    biche = lorraine.get_story_paragraphs(BICHE)
    jean = lorraine.get_story_paragraphs(JEAN)
    lorraine.get_story_paragraphs(BICHE)

    assert len(gutenberg.requests) == 1
    assert biche[0].startswith("Il était une fois un roi qui voulait se marier")
    assert jean[0].startswith("On envoya le petit garçon à l'école")


def test_the_cache_holds_each_storys_text_not_the_page(lorraine, gutenberg):
    lorraine.get_story_paragraphs(BICHE)

    files = cache_files(lorraine)
    assert len(files) == 4  # LE FOLLET is not in the cut-down page
    for name in files:
        with open(os.path.join(lorraine._story_cache.directory, name), encoding="utf-8") as f:
            record = json.load(f)
        assert set(record) == {"format", "url", "anchor", "fetched_at", "last_modified", "paragraphs"}
        assert record["format"] == skill_module.CACHE_FORMAT
        assert record["last_modified"] == LAST_MODIFIED
        assert not any("<" in p for p in record["paragraphs"])


def test_the_cache_outlives_the_process(lorraine, gutenberg):
    expected = lorraine.get_story_paragraphs(JEAN)

    lorraine._init_story_cache(lorraine._story_cache.directory)  # a restart: nothing in memory
    assert lorraine.get_story_paragraphs(JEAN) == expected
    assert len(gutenberg.requests) == 1


def test_a_cache_written_by_another_format_is_fetched_again(lorraine, gutenberg, monkeypatch):
    lorraine.get_story_paragraphs(BICHE)
    files = cache_files(lorraine)

    monkeypatch.setattr(skill_module, "CACHE_FORMAT", skill_module.CACHE_FORMAT + 1)
    lorraine._init_story_cache(lorraine._story_cache.directory)
    lorraine.get_story_paragraphs(BICHE)

    assert len(gutenberg.requests) == 2
    # an extractor change must not be answered with a 304
    assert "If-Modified-Since" not in gutenberg.requests[1]["headers"]
    assert cache_files(lorraine) == files  # rewritten in place, not added to


def test_a_cache_entry_for_another_anchor_is_a_miss(lorraine, gutenberg):
    lorraine.get_story_paragraphs(BICHE)

    moved = dict(BICHE, anchor="XCIX")
    assert lorraine._story_cache.get(URL, moved["anchor"]) is None


def test_a_stale_story_is_asked_for_with_if_modified_since(lorraine, gutenberg):
    expected = lorraine.get_story_paragraphs(BICHE)
    age_cache(lorraine, skill_module.CACHE_MAX_AGE + 60)
    gutenberg.pages[URL] = lambda headers: response(status=304)

    assert lorraine.get_story_paragraphs(BICHE) == expected
    assert gutenberg.requests[1]["headers"]["If-Modified-Since"] == LAST_MODIFIED
    # the 304 renewed every story of that book, so none is asked for again
    lorraine.get_story_paragraphs(JEAN)
    assert len(gutenberg.requests) == 2


def test_a_stale_story_is_replaced_when_the_book_changed(lorraine, gutenberg):
    lorraine.get_story_paragraphs(BICHE)
    age_cache(lorraine, skill_module.CACHE_MAX_AGE + 60)
    changed = fixture_page("contes-de-lorraine.html").replace(b"voulait se marier", b"voulait prendre femme")
    gutenberg.pages[URL] = response(changed, last_modified="Sun, 09 Nov 2025 20:12:36 GMT")

    assert "un roi qui voulait prendre femme" in lorraine.get_story_paragraphs(BICHE)[0]
    assert lorraine._story_cache.get(URL, BICHE["anchor"])["last_modified"] == "Sun, 09 Nov 2025 20:12:36 GMT"


def test_a_stale_copy_is_read_when_gutenberg_does_not_answer(lorraine, gutenberg):
    expected = lorraine.get_story_paragraphs(BICHE)
    age_cache(lorraine, skill_module.CACHE_MAX_AGE + 60)
    gutenberg.pages[URL] = requests.ConnectionError("down")

    assert lorraine.get_story_paragraphs(BICHE) == expected
    lorraine.log.warning.assert_called_once()


def test_a_failed_fetch_is_not_retried_before_the_backoff(lorraine, gutenberg):
    gutenberg.pages[URL] = requests.ConnectionError("down")

    with pytest.raises(StoryFetchError, match="down"):
        lorraine.get_story_paragraphs(BICHE)
    # the same book, another story: no request
    with pytest.raises(StoryFetchError, match="not trying again"):
        lorraine.get_story_paragraphs(JEAN)
    assert len(gutenberg.requests) == 1

    end_backoff(lorraine)
    gutenberg.pages[URL] = book()
    assert lorraine.get_story_paragraphs(JEAN)
    assert len(gutenberg.requests) == 2


def test_an_http_error_is_a_failed_fetch(lorraine, gutenberg):
    gutenberg.pages[URL] = response(b"gone", status=404)

    with pytest.raises(StoryFetchError, match="404"):
        lorraine.get_story_paragraphs(BICHE)
    with pytest.raises(StoryFetchError, match="not trying again"):
        lorraine.get_story_paragraphs(BICHE)
    assert len(gutenberg.requests) == 1


def test_a_story_its_page_does_not_yield_does_not_refetch_the_book(lorraine, gutenberg):
    with pytest.raises(StoryFetchError, match="heading VI not found"):
        lorraine.get_story_paragraphs(FOLLET)
    with pytest.raises(StoryFetchError, match="heading VI not found"):
        lorraine.get_story_paragraphs(FOLLET)
    assert len(gutenberg.requests) == 1


def test_reading_works_when_the_cache_directory_cannot_be_written(lorraine, gutenberg, tmp_path):
    not_a_directory = tmp_path / "not-a-directory"
    not_a_directory.write_text("")
    lorraine._init_story_cache(str(not_a_directory / "story-cache"))

    assert lorraine.get_story_paragraphs(BICHE)[0].startswith("Il était une fois un roi")
    # the rest of that book is kept in memory: no second request for it
    assert lorraine.get_story_paragraphs(JEAN)[0].startswith("On envoya le petit garçon")
    assert len(gutenberg.requests) == 1
    lorraine.log.warning.assert_called_once()


def test_the_user_agent_names_the_skill_its_version_and_repo(lorraine, gutenberg):
    lorraine.get_story_paragraphs(BICHE)

    sent = gutenberg.requests[0]
    user_agent = sent["headers"]["User-Agent"]
    assert user_agent == skill_module.USER_AGENT
    assert user_agent.startswith(f"ovos-skill-cosquin-tales/{skill_module.SKILL_VERSION} ")
    assert "(+https://github.com/andlo/ovos-skill-cosquin-tales)" in user_agent
    assert "If-Modified-Since" not in sent["headers"]
    assert sent["timeout"] == skill_module.FETCH_TIMEOUT


def test_the_cache_is_in_the_skills_xdg_cache_directory(skill, monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    skill._init_story_cache()
    assert skill._story_cache.directory == os.path.join(get_xdg_cache_save_path(), "skills", skill.skill_id)
    assert skill._story_cache.directory.startswith(str(tmp_path / "xdg"))
    assert not os.path.exists(skill._story_cache.directory)  # made on first use


def test_no_parsed_page_is_kept(lorraine, gutenberg):
    gc.collect()
    before = sum(isinstance(o, BeautifulSoup) for o in gc.get_objects())
    lorraine.get_story_paragraphs(BICHE)
    assert sum(isinstance(o, BeautifulSoup) for o in gc.get_objects()) == before


def test_two_stories_of_one_book_asked_at_once_fetch_it_once(lorraine, gutenberg):
    def slow_book(headers):
        time.sleep(0.2)
        return book()
    gutenberg.pages[URL] = slow_book
    results = {}
    threads = [threading.Thread(target=lambda e=e: results.update({e["anchor"]: lorraine.get_story_paragraphs(e)}))
               for e in (BICHE, JEAN)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 2
    assert len(gutenberg.requests) == 1


def test_fetch_content_reply_keeps_its_shape(lorraine, gutenberg):
    lorraine.handle_fetch_content(make_message({"content_id": "LA BICHE BLANCHE"}))

    sent = lorraine.bus.emit.call_args[0][0]
    assert sent.msg_type == "ovos.common_reading.fetch_content.response"
    assert list(sent.data) == ["paragraphs"]
    assert sent.data["paragraphs"][-1].endswith("vécut heureux avec sa femme.")

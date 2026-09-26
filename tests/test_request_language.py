"""The language of each request decides whether this provider answers -
not the device's language. On a HiveMind hub one ovos-core serves many
users at once, each session in its own language: a French session must
get these stories even on a hub whose own language is English, and an
English session must not get French stories on a French hub."""
import pytest
from ovos_bus_client.message import Message
from ovos_bus_client.session import Session

from conftest import COMMON_READING_SEARCH_RESPONSE, COMMON_READING_FETCH_CONTENT_RESPONSE, COMMON_READING_PONG

INDEX = {"LA BICHE BLANCHE": {"url": "http://x/book", "anchor": "XIV"}}


def request(msg_type, data=None, session_lang=None):
    context = {}
    if session_lang:
        context["session"] = Session("a-hivemind-client", lang=session_lang).serialize()
    return Message(msg_type, data or {}, context)


def search(skill, session_lang=None, **data):
    skill.index = INDEX
    skill.bus.emit.reset_mock()
    skill.handle_search(request("ovos.common_reading.search", dict({"phrase": "la biche blanche"}, **data), session_lang))
    return [c[0][0] for c in skill.bus.emit.call_args_list]


def ping(skill, session_lang=None, **data):
    skill.bus.emit.reset_mock()
    skill.handle_ping(request("ovos.common_reading.ping", dict({"requester": "test"}, **data), session_lang))
    return [c[0][0] for c in skill.bus.emit.call_args_list]


@pytest.fixture
def english_hub(skill, monkeypatch):
    monkeypatch.setattr(type(skill), "lang", "en-us", raising=False)
    return skill


@pytest.mark.parametrize("session_lang", ["fr-FR", "fr-CA", "fr"])
def test_french_session_on_an_english_hub_gets_an_answer(english_hub, session_lang):
    sent = search(english_hub, session_lang=session_lang)
    assert len(sent) == 1
    assert sent[0].msg_type == COMMON_READING_SEARCH_RESPONSE
    assert sent[0].data["content_id"] == "LA BICHE BLANCHE"


def test_english_session_on_a_french_hub_gets_no_answer(skill):
    # the conftest fixture runs the skill on an fr-fr device
    assert search(skill, session_lang="en-US") == []


def test_lang_field_wins_over_the_session(english_hub):
    assert len(search(english_hub, session_lang="en-US", lang="fr-fr")) == 1
    assert search(english_hub, session_lang="fr-FR", lang="en-us") == []


@pytest.mark.parametrize("lang", ["fr-fr", "fr-CA", "FR", "fr_be"])
def test_lang_field_is_compared_on_the_primary_subtag(english_hub, lang):
    assert len(search(english_hub, lang=lang)) == 1


@pytest.mark.parametrize("lang", ["en-us", "de-de", "da-dk", "es"])
def test_lang_field_in_another_language_gets_no_answer(skill, lang):
    assert search(skill, lang=lang) == []


def test_request_without_a_language_falls_back_to_the_device_language(skill, monkeypatch):
    """An older pipeline plugin sends neither 'lang' nor a session."""
    assert len(search(skill)) == 1
    monkeypatch.setattr(type(skill), "lang", "en-us", raising=False)
    assert search(skill) == []


def test_random_story_is_only_offered_in_french(english_hub):
    assert search(english_hub, session_lang="en-US", phrase=None) == []
    sent = search(english_hub, session_lang="fr-FR", phrase=None)
    assert len(sent) == 1 and sent[0].data["confidence"] == 0.9


def test_ping_without_a_language_is_answered(english_hub):
    sent = ping(english_hub)
    assert len(sent) == 1 and sent[0].msg_type == COMMON_READING_PONG


def test_ping_in_another_language_is_not_answered(skill):
    assert ping(skill, lang="en-us") == []
    assert ping(skill, session_lang="de-DE") == []


def test_ping_in_french_is_answered(english_hub):
    assert len(ping(english_hub, lang="fr-ca")) == 1
    assert len(ping(english_hub, session_lang="fr-FR")) == 1


def test_fetch_is_answered_whatever_the_language(skill):
    """A fetch is addressed to this provider by skill_id and the plugin
    waits for its reply - it is never gated on language."""
    skill.index = INDEX
    skill.get_story_paragraphs = lambda entry: ["Il était une fois."]
    skill.handle_fetch_content(request(
        f"ovos.common_reading.fetch_content.{skill.skill_id}",
        {"content_id": "LA BICHE BLANCHE", "lang": "en-us"}, "en-US"))
    sent = skill.bus.emit.call_args[0][0]
    assert sent.msg_type == COMMON_READING_FETCH_CONTENT_RESPONSE
    assert sent.data["paragraphs"] == ["Il était une fois."]

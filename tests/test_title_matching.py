"""Title matching against the real bundled index (30 stories). The book
prints every title in capitals, so case, accents, punctuation, '&' and a
leading article must not matter - and the title is spoken in ordinary
case, not shouted in capitals."""
import pytest
from ovos_bus_client.message import Message

from conftest import normalize_title, title_aliases, spoken_title

CONFIRMATION_THRESHOLD = 0.8  # the pipeline plugin asks "is it that one?" below this


@pytest.fixture
def indexed(skill):
    skill.index = skill._load_index()
    return skill


@pytest.mark.parametrize("phrase", [
    # used to score 0.14
    "la biche blanche",
    "LA BICHE BLANCHE",
    "La Biche Blanche",
    "biche blanche",
])
def test_exact_title_in_any_case(indexed, phrase):
    assert indexed._best_title(phrase) == ("LA BICHE BLANCHE", 1.0)


@pytest.mark.parametrize("phrase, expected", [
    ("l'oiseau de vérité", "L'OISEAU DE VÉRITÉ"),
    ("l'oiseau de verite", "L'OISEAU DE VÉRITÉ"),
    ("jean de l'ours", "JEAN DE L'OURS"),
    ("jeanne et brimboriau", "JEANNE & BRIMBORIAU"),
    ("le roi d'angleterre et son filleul", "LE ROI D'ANGLETERRE & SON FILLEUL"),
    ("les fils du pêcheur", "LES FILS DU PÊCHEUR"),
    ("la bourse", "LA BOURSE, LE SIFFLET & LE CHAPEAU"),
])
def test_name_people_use_finds_the_title(indexed, phrase, expected):
    title, score = indexed._best_title(phrase)
    assert title == expected
    assert score >= 0.95


def test_close_spelling_still_confident(indexed):
    title, score = indexed._best_title("la pouillotte et le coucherilot")
    assert title == "LA POUILLOTTE & LE COUCHERILLOT"
    assert score >= CONFIRMATION_THRESHOLD


def test_one_shared_word_is_not_enough_to_skip_the_confirmation(indexed):
    """'la belle et la bête' is not in this collection; 'LA LAIDE & LA
    BELLE' shares one of its two words."""
    _, score = indexed._best_title("la belle et la bête")
    assert score < CONFIRMATION_THRESHOLD


def test_search_response_speaks_the_title_in_ordinary_case(indexed):
    indexed.handle_search(Message("ovos.common_reading.search", {"phrase": "la biche blanche"}))
    sent = indexed.bus.emit.call_args[0][0]
    assert sent.data["content_id"] == "LA BICHE BLANCHE"
    assert sent.data["title"] == "La Biche Blanche"
    assert sent.data["confidence"] == 1.0


def test_fetch_uses_the_content_id_from_the_search(indexed):
    indexed.get_story_paragraphs = lambda entry: [entry["anchor"]]
    indexed.handle_search(Message("ovos.common_reading.search", {"phrase": "jeanne et brimboriau"}))
    content_id = indexed.bus.emit.call_args[0][0].data["content_id"]
    indexed.handle_fetch_content(Message("ovos.common_reading.fetch_content.x", {"content_id": content_id}))
    assert indexed.bus.emit.call_args[0][0].data["paragraphs"] == ["XXII"]


@pytest.mark.parametrize("title, expected", [
    ("LA BICHE BLANCHE", "La Biche Blanche"),
    ("JEAN DE L'OURS", "Jean de l'Ours"),
    ("L'OISEAU DE VÉRITÉ", "L'Oiseau de Vérité"),
    ("LE ROI D'ANGLETERRE & SON FILLEUL", "Le Roi d'Angleterre et son Filleul"),
    ("LES TROCS DE JEAN-BAPTISTE", "Les Trocs de Jean-Baptiste"),
    ("LES DEUX SOLDATS DE 1689", "Les Deux Soldats de 1689"),
    ("Déjà écrit", "Déjà écrit"),
])
def test_spoken_title(title, expected):
    assert spoken_title(title) == expected


def test_every_bundled_title_is_spoken_without_capitals_only(indexed):
    for title in indexed.index:
        spoken = spoken_title(title)
        assert not spoken.isupper(), spoken
        assert "&" not in spoken


@pytest.mark.parametrize("text, expected", [
    ("LA BICHE BLANCHE", "biche blanche"),
    ("L'OISEAU DE VÉRITÉ", "oiseau de verite"),
    ("JEANNE & BRIMBORIAU", "jeanne et brimboriau"),
    ("LE POIRIER D'OR", "poirier d or"),
    ("le poirier d'or", "poirier d or"),
])
def test_normalize_title(text, expected):
    assert normalize_title(text) == expected


def test_title_aliases_of_a_title_with_a_comma():
    aliases = dict(title_aliases("LA BOURSE, LE SIFFLET & LE CHAPEAU"))
    assert aliases["bourse le sifflet et le chapeau"] == 1.0
    assert aliases["bourse"] < 1.0

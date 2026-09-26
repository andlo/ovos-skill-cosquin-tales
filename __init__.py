"""
skill OVOS Cosquin Tales
Copyright (C) 2026  Andreas Lorensen

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

---

Provider skill for ovos-common-reading-pipeline-plugin: implements the
ovos.common_reading.* bus protocol and registers NO intents of its own.
See https://github.com/andlo/ovos-common-reading-pipeline-plugin for the
full protocol - this skill has no standalone voice interface, it needs
the pipeline plugin installed and configured to be useful.

The story INDEX (title/anchor per story) is bundled with this package
(see locale/fr-fr/index.json), built once via scripts/build_index.py -
browsing/matching needs no internet at all. Internet is only needed when
actually fetching a specific story's text from Project Gutenberg.
"""

from ovos_workshop.skills import OVOSSkill
from ovos_bus_client.session import SessionManager
from ovos_utils.parse import match_one, fuzzy_match
from ovos_utils import classproperty
from ovos_utils.process_utils import RuntimeRequirements

import requests
from bs4 import BeautifulSoup
from functools import lru_cache
import re
import json
import os
import random
import unicodedata


class StoryFetchError(Exception):
    """Raised when a story could not be fetched or parsed from
    Project Gutenberg."""


COMMON_READING_SEARCH = "ovos.common_reading.search"
COMMON_READING_SEARCH_RESPONSE = "ovos.common_reading.search.response"
COMMON_READING_FETCH_CONTENT = "ovos.common_reading.fetch_content"  # + ".{this_skill_id}"
COMMON_READING_FETCH_CONTENT_RESPONSE = "ovos.common_reading.fetch_content.response"
COMMON_READING_PING = "ovos.common_reading.ping"
COMMON_READING_PONG = "ovos.common_reading.pong"

COLLECTION_ALIASES = ["cosquin", "lorraine", "lorraine tales", "contes de lorraine",
                       "emmanuel cosquin"]
COLLECTION_HINT_THRESHOLD = 0.85
CONTENT_TYPES = ["story", "tale"]
AUTHOR_NAME = "collected by Emmanuel Cosquin"
COLLECTION_NAME = "Contes populaires de Lorraine"
SOURCE_NAME = "Project Gutenberg"

# Cosquin's Lorraine folk tales are only sourced in French (see README)
# and this provider does NOT translate (unlike ovos-skill-ovosblog/
# ovos-skill-arxiv-papers) - it answers searches made in French and stays
# silent for every other language. That is decided per request, not once
# from the device's language: on a HiveMind hub one ovos-core serves many
# users at once, each session in its own language, so the provider always
# loads and looks at the language each search was made in (see
# _request_lang()). Same pattern as ovos-skill-andrew-lang-tales/
# ovos-skill-bechstein-tales, just for 'fr'.
SUPPORTED_LANGUAGES = {"fr"}

# 'raconte-moi une histoire' names no title: answer with a random one,
# confident enough to be read without an "is it that one?" round trip
# (the plugin asks below 0.8) but below the 1.0 of a title somebody
# actually named
RANDOM_STORY_CONFIDENCE = 0.9

# title matching ignores case, accents, punctuation and a leading
# article, on both the request and the title - the book prints every
# title in capitals, so 'la biche blanche', 'biche blanche' and 'LA
# BICHE BLANCHE' all compare as 'biche blanche', and "l'oiseau de
# vérité" as 'oiseau de verite'
LEADING_ARTICLES = ("le", "la", "les", "l", "un", "une")
TITLE_PREFIXES = ()  # none of these titles has a 'The Story Of' kind of prefix
AND_WORD = "et"  # what '&' is read as - 'JEANNE & BRIMBORIAU'
OR_WORD = "ou"
# the part before a title's first comma is how people often ask for it
# ('la bourse') - trusted a little less than the whole title, so a
# provider holding a story that is called exactly that still wins
PARTIAL_TITLE_WEIGHT = 0.95
# words that say nothing about which title was meant, half the titles
# have them ('le tailleur et le geant' is told apart by 'tailleur' and
# 'geant') - accents already dropped, 'a' is 'à'
FILLER_WORDS = set(LEADING_ARTICLES) | {"et", "ou", "de", "du", "des", "d", "a", "au", "aux",
                                        "en", "son", "sa", "ses"}
# two words are the same word when they are at least this alike
# ('coucherilot'/'coucherillot', 'pecheurs'/'pecheur')
SAME_WORD_THRESHOLD = 0.9
# spoken titles keep these lower case after the first word, the way a
# French title is written ('Le Roi d'Angleterre et son Filleul')
LOWERCASE_TITLE_WORDS = {"de", "du", "des", "d", "l", "la", "le", "les", "et",
                         "à", "au", "aux", "en", "son", "sa", "ses", "un", "une"}


def primary_subtag(lang):
    """'en-US', 'en_gb', 'EN' -> 'en'."""
    return (lang or "").replace("_", "-").split("-")[0].lower()


def title_words(text):
    """Casefolded words, accents and punctuation dropped, '&' read as
    AND_WORD."""
    text = unicodedata.normalize("NFKD", text.casefold().replace("&", f" {AND_WORD} "))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[\W_]+", " ", text).split()


def normalize_title(text):
    """Reduce a title (or what somebody asked for) to what matters for
    matching: its title_words(), without a leading article or one of
    TITLE_PREFIXES."""
    words = title_words(text)

    def drop_article(words):
        return words[1:] if len(words) > 1 and words[0] in LEADING_ARTICLES else words

    words = drop_article(words)
    for prefix in TITLE_PREFIXES:
        prefix = title_words(prefix)
        if len(words) > len(prefix) and words[:len(prefix)] == prefix:
            words = drop_article(words[len(prefix):])
            break
    return " ".join(words)


def significant_words(title):
    """The words of a normalized title that say which title it is -
    FILLER_WORDS are shared by half the titles and say nothing, unless
    the title has nothing else."""
    words = title.split()
    return [w for w in words if w not in FILLER_WORDS] or words


def same_word(a, b):
    if a == b:
        return True
    # a ratio can never beat the length ratio - skip the ones that cannot
    # make it before paying for the comparison
    if 2 * min(len(a), len(b)) < SAME_WORD_THRESHOLD * (len(a) + len(b)):
        return False
    return fuzzy_match(a, b) >= SAME_WORD_THRESHOLD


def title_similarity(wanted, alias):
    """How alike two normalized titles are, 0.0-1.0: the letter-level
    ratio averaged with the share of significant_words() that have a
    close match on the other side. Letters alone are too generous - 'la
    belle et la bête' and 'LA LAIDE & LA BELLE' are 0.73 alike letter by
    letter but share one of two words (0.61 together). Spaces do not
    count."""
    if wanted.replace(" ", "") == alias.replace(" ", ""):
        return 1.0
    a, b = significant_words(wanted), significant_words(alias)
    shared = sum(any(same_word(w, o) for o in b) for w in a) + \
        sum(any(same_word(w, o) for o in a) for w in b)
    return (fuzzy_match(wanted, alias) + shared / (len(a) + len(b))) / 2


def spoken_title(title):
    """The book prints every title in capitals ('LE ROI D'ANGLETERRE &
    SON FILLEUL') and the index keeps them that way, since they are the
    content_id. A TTS engine may spell capitals out letter by letter, so
    the title that gets spoken is in ordinary case, articles and
    prepositions lower case after the first word: 'Le Roi d'Angleterre
    et son Filleul'. A title that is not all capitals is left alone."""
    if not title.isupper():
        return title
    first = True

    def case(match):
        nonlocal first
        word = match.group(0).lower()
        if not first and word in LOWERCASE_TITLE_WORDS:
            return word
        first = False
        return word[0].upper() + word[1:]

    return re.sub(r"[^\W\d_]+", case, title.replace("&", AND_WORD))


@lru_cache(maxsize=None)
def title_aliases(title):
    """Every way a title can be asked for, normalized, each with the
    weight its match counts for: the whole title, and at
    PARTIAL_TITLE_WEIGHT each half of an 'X, ou Y' / 'X; Y' / 'X. Y'
    title and the part before its first comma ('LA BOURSE, LE SIFFLET &
    LE CHAPEAU' can be asked for as 'la bourse'). Anything in
    parentheses is not part of the name."""
    whole = re.sub(r"\([^)]*\)", " ", title)
    aliases = {normalize_title(title): 1.0, normalize_title(whole): 1.0}
    parts = re.split(rf"[;:.]|\b{OR_WORD}\b", whole, flags=re.IGNORECASE)
    parts.append(whole.split(",")[0])
    for part in parts:
        alias = normalize_title(part)
        if alias and alias not in aliases:
            aliases[alias] = PARTIAL_TITLE_WEIGHT
    aliases.pop("", None)
    return tuple(aliases.items())


class CosquinTales(OVOSSkill):

    @classproperty
    def runtime_requirements(self):
        return RuntimeRequirements(
            internet_before_load=False,
            network_before_load=False,
            requires_internet=False,
            requires_network=False,
            no_internet_fallback=True,
            no_network_fallback=True,
        )

    def initialize(self):
        # always loads, whatever the device language: which language a
        # search is in is decided per request (see handle_search())
        self._book_soup_cache = {}
        self.index = self._load_index()
        if not self.index:
            self.log.error("No bundled story index found")
        self.log.info(
            f"{self.skill_id}: serving {len(self.index)} French stories "
            f"to searches made in French (fr-*), whatever the device "
            f"language ('{self.lang}') is"
        )
        self.add_event(COMMON_READING_SEARCH, self.handle_search)
        self.add_event(f"{COMMON_READING_FETCH_CONTENT}.{self.skill_id}", self.handle_fetch_content)
        self.add_event(COMMON_READING_PING, self.handle_ping)

    def _load_index(self):
        path = os.path.join(os.path.dirname(__file__), "locale", "fr-fr", "index.json")
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            self.log.error(f"could not read bundled story index {path}: {e}")
            return {}

    def _get_book_soup(self, url):
        if url in self._book_soup_cache:
            return self._book_soup_cache[url]
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")
        except requests.RequestException as e:
            raise StoryFetchError(f"failed to fetch {url}: {e}") from e
        self._book_soup_cache[url] = soup
        return soup

    def get_story_paragraphs(self, entry):
        """Extract a single story's paragraphs. Each story is a flat
        sequence of <p> siblings after its <h2 id='ROMAN_NUMERAL'> -
        collection stops at the next <h2> (next story) OR <h3> (the
        'REMARQUES' scholarly commentary that follows every story here,
        comparing it to variants from other regions - genuinely
        interesting to a folklorist, but not part of the tale itself and
        not something to read aloud as if it were)."""
        soup = self._get_book_soup(entry["url"])
        h2 = soup.find("h2", {"id": entry["anchor"]})
        if h2 is None:
            raise StoryFetchError(f"heading {entry['anchor']} not found in {entry['url']}")
        paragraphs = []
        for el in h2.find_all_next():
            if el.name in ("h2", "h3"):
                break
            if el.name == "p":
                text = re.sub(r"\s+", " ", el.get_text(strip=True)).strip()
                if text:
                    paragraphs.append(text)
        if not paragraphs:
            raise StoryFetchError(f"no story text found at {entry['url']}#{entry['anchor']}")
        return paragraphs

    def _matches_collection_hint(self, hint):
        if not hint:
            return True
        _, score = match_one(hint.lower(), COLLECTION_ALIASES)
        return score >= COLLECTION_HINT_THRESHOLD

    def _matches_content_type(self, content_type):
        if not content_type:
            return True
        return content_type.lower() in CONTENT_TYPES

    @staticmethod
    def _request_lang(message):
        """The language a request was made in, or None when it does not
        say: the pipeline plugin's own 'lang' field first, then the
        language of the session the request was forwarded from (a
        HiveMind client's, on a hub). An older plugin sends neither."""
        lang = message.data.get("lang") or message.context.get("lang")
        if not lang and message.context.get("session"):
            lang = SessionManager.get(message).lang
        return lang or None

    @staticmethod
    def _serves(lang):
        return primary_subtag(lang) in SUPPORTED_LANGUAGES

    def _best_title(self, phrase):
        """(title, confidence) of the story that best matches what was
        asked for, or (None, 0.0) when the phrase is empty once
        normalized - see normalize_title() and title_aliases()."""
        wanted = normalize_title(phrase)
        best, best_score = None, 0.0
        if not wanted:
            return best, best_score
        for title in self.index:
            for alias, weight in title_aliases(title):
                score = title_similarity(wanted, alias) * weight
                if score > best_score:
                    best, best_score = title, score
        return best, best_score

    def handle_search(self, message):
        if not self.index:
            return
        # a search made in any other language gets no answer at all, not
        # an empty one - the plugin just collects whatever arrives. With
        # no language on the request (an older plugin), the device's own
        # language decides, as it always did.
        if not self._serves(self._request_lang(message) or self.lang):
            return
        collection_hint = message.data.get("collection_hint")
        if not self._matches_collection_hint(collection_hint):
            return
        content_type = message.data.get("content_type")
        if not self._matches_content_type(content_type):
            return

        phrase = (message.data.get("phrase") or "").strip()
        title, confidence = self._best_title(phrase) if phrase else (None, 0.0)
        if title is None:
            # no title asked for: 'tell me a story', or 'a story from
            # Cosquin' - a random one, and fully confident when the
            # collection itself was named
            title = random.choice(list(self.index.keys()))
            confidence = 1.0 if collection_hint else RANDOM_STORY_CONFIDENCE

        self.bus.emit(message.reply(COMMON_READING_SEARCH_RESPONSE, {
            "skill_id": self.skill_id,
            "content_id": title,
            "title": spoken_title(title),
            "author": AUTHOR_NAME,
            "collection": COLLECTION_NAME,
            "source": SOURCE_NAME,
            "confidence": confidence,
        }))

    def handle_fetch_content(self, message):
        content_id = message.data.get("content_id")
        entry = self.index.get(content_id)
        if not entry:
            self.bus.emit(message.reply(COMMON_READING_FETCH_CONTENT_RESPONSE, {"paragraphs": []}))
            return
        try:
            paragraphs = self.get_story_paragraphs(entry)
        except StoryFetchError as e:
            self.log.error(f"Could not fetch story '{content_id}': {e}")
            self.bus.emit(message.reply(COMMON_READING_FETCH_CONTENT_RESPONSE, {"paragraphs": []}))
            return
        self.bus.emit(message.reply(COMMON_READING_FETCH_CONTENT_RESPONSE, {"paragraphs": paragraphs}))

    def handle_ping(self, message):
        """Cheap 'is anyone there?' reply - no index lookup. Only ever
        called by the pipeline plugin on its rare 0-candidates path
        (see ovos-common-reading-pipeline-plugin#2), never on every
        search. A ping that says which language it is asking for (its
        'lang' field or the session it was forwarded from) only gets a
        pong when that is French, so the plugin can tell 'nothing
        installed for this language' from 'found nothing'. A ping that
        does not say is answered: this provider is installed."""
        lang = self._request_lang(message)
        if lang and not self._serves(lang):
            return
        self.bus.emit(message.reply(COMMON_READING_PONG, {
            "skill_id": self.skill_id,
            "collection": COLLECTION_NAME,
        }))

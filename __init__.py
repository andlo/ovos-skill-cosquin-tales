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
from ovos_utils.parse import match_one
from ovos_utils import classproperty
from ovos_utils.process_utils import RuntimeRequirements

import requests
from bs4 import BeautifulSoup
import re
import json
import os
import random


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
# ovos-skill-arxiv-papers) - a device set to any other language gets no
# response at all, decided once at load time (see initialize()). Same
# load-time-gate pattern as ovos-skill-andrew-lang-tales/
# ovos-skill-bechstein-tales, just for 'fr'.
SUPPORTED_LANGUAGES = {"fr"}


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
        lang = self.lang.split("-")[0]
        if lang not in SUPPORTED_LANGUAGES:
            self.log.info(
                f"{self.skill_id}: device language '{self.lang}' is not "
                f"French, and this provider (Cosquin's Lorraine folk "
                f"tales, Project Gutenberg) has no non-French content and "
                f"does not translate - skill will stay inert (no bus "
                f"events registered, index not loaded)."
            )
            self.index = {}
            return
        self._book_soup_cache = {}
        self.index = self._load_index()
        if not self.index:
            self.log.error("No bundled story index found")
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

    def handle_search(self, message):
        if not self.index:
            return
        collection_hint = message.data.get("collection_hint")
        if not self._matches_collection_hint(collection_hint):
            return
        content_type = message.data.get("content_type")
        if not self._matches_content_type(content_type):
            return

        phrase = message.data.get("phrase")
        if phrase:
            title, confidence = match_one(phrase, list(self.index.keys()))
        elif collection_hint:
            title = random.choice(list(self.index.keys()))
            confidence = 1.0
        else:
            return

        self.bus.emit(message.reply(COMMON_READING_SEARCH_RESPONSE, {
            "skill_id": self.skill_id,
            "content_id": title,
            "title": title,
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
        search. A non-French device never reaches this handler at all,
        since initialize() returned early and never registered it -
        which is exactly the right behavior."""
        self.bus.emit(message.reply(COMMON_READING_PONG, {
            "skill_id": self.skill_id,
            "collection": COLLECTION_NAME,
        }))

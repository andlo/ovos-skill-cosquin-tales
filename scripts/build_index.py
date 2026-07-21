#!/usr/bin/env python3
"""Builds locale/fr-fr/index.json - a bundled title -> {url, anchor}
mapping for Emmanuel Cosquin's "Contes populaires de Lorraine" (Project
Gutenberg #57892, volume 1 of 2).

Book structure (verified by hand before writing this script): the whole
volume is one HTML page. Each story is a `<h2 id="ROMAN_NUMERAL">`
(e.g. id="I", "II", ...) containing the roman numeral + the title, and
its <p> paragraphs follow as direct siblings until the next <h2> OR
<h3> - each story is followed by a "REMARQUES" (scholarly commentary,
comparing the tale to variants from other regions) marked with an <h3>,
which must NOT be included in what gets read aloud.

KNOWN GAP: volume 2 (ebook #50838) uses a different, page-number-based
anchor scheme (`<a id="Page_N">` nested inside an unlabelled <h2>,
rather than the h2 itself carrying a roman-numeral id) - the same class
of problem that excluded the Olive Fairy Book from
ovos-skill-andrew-lang-tales. Not handled here yet; volume 1 alone is
still 30 real stories. Tracked as a follow-up issue."""
import json
import re
import requests
from bs4 import BeautifulSoup

BOOK_URL = "https://www.gutenberg.org/ebooks/57892.html.images"
ROMAN_NUMERAL_RE = re.compile(r"^[IVXLCM]+$")


def build_index():
    r = requests.get(BOOK_URL, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    index = {}
    for h2 in soup.find_all("h2"):
        anchor = h2.get("id")
        if not anchor or not ROMAN_NUMERAL_RE.match(anchor):
            continue  # not a story (front matter, appendices, TOC, ...)
        full_text = h2.get_text(" ", strip=True)
        title = full_text.removeprefix(anchor).strip()
        if not title:
            # rare quirk (one entry, 'XVIII'): the real title only shows
            # up in the h2's title="" HTML attribute, not its visible
            # text - fall back to that before giving up
            title_attr = (h2.get("title") or "").strip()
            title = title_attr.removeprefix(anchor).strip()
        if not title:
            print(f"  skipping '{anchor}' - no title text found")
            continue
        index[title] = {"url": BOOK_URL, "anchor": anchor}

    return index


if __name__ == "__main__":
    index = build_index()
    print(f"Built index with {len(index)} stories")
    with open("locale/fr-fr/index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2, sort_keys=True)
    print("Wrote locale/fr-fr/index.json")

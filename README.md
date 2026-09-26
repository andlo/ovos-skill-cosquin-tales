# <img src='story-512.png' card_color='#40DBB0' width='50' height='50' style='vertical-align:bottom'/> Cosquin Tales (provider)

A *provider* skill for [ovos-common-reading-pipeline-plugin](https://github.com/andlo/ovos-common-reading-pipeline-plugin),
delivering Emmanuel Cosquin's collection of Lorraine (French regional)
folk tales.

A genuinely different register than `ovos-skill-perrault-tales`-style
literary fairy tales: these are folk-collected, with the collector's own
comparative scholarly notes ("Remarques") on how each tale relates to
variants told elsewhere in France and abroad (excluded from what's read
aloud - see below).

[![Tests](https://github.com/andlo/ovos-skill-cosquin-tales/actions/workflows/test.yml/badge.svg)](https://github.com/andlo/ovos-skill-cosquin-tales/actions/workflows/test.yml)
[![PyPI version](https://img.shields.io/pypi/v/ovos-skill-cosquin-tales.svg)](https://pypi.org/project/ovos-skill-cosquin-tales/)

> **This skill has no standalone voice interface.** It registers no
> intents and never speaks. It only answers
> [ovos.common_reading.* bus messages](https://github.com/andlo/ovos-common-reading-pipeline-plugin#the-ovoscommon_reading-bus-protocol),
> so you also need **ovos-common-reading-pipeline-plugin** installed and
> added to your pipeline config for it to be useful at all.

> **French only, no translation.** Same situation as
> `ovos-skill-andrew-lang-tales`/`ovos-skill-bechstein-tales`, just for
> French. **It answers searches made in French (`fr-*`) and stays
> silent for every other language**, whatever the device's own language
> is (see "Languages" below).

## Install
```bash
pip install ovos-skill-cosquin-tales ovos-common-reading-pipeline-plugin
```

## Story index

The story index (title, anchor per story) is **bundled with this
package** (`locale/fr-fr/index.json`), not scraped live - browsing/
matching needs no internet at all. Only fetching a specific story's
actual text (once chosen) needs a live request to Project Gutenberg.

**30 stories** from volume 1 of Cosquin's "Contes populaires de
Lorraine" (Project Gutenberg ebook #57892). The index was built via
`scripts/build_index.py`, which scans for `<h2 id="ROMAN_NUMERAL">`
headings (the book's own per-story anchoring) and excludes non-story
sections (front matter, appendices) by requiring the id to actually look
like a Roman numeral.

**Known gap: volume 2 not included.** Volume 2 (ebook #50838) uses a
different, page-number-based anchor scheme (`<a id="Page_N">` nested
inside an unlabelled `<h2>`, rather than the h2 itself carrying a
roman-numeral id) - the same class of problem that excluded the *Olive
Fairy Book* from `ovos-skill-andrew-lang-tales`. Not handled yet; a
follow-up could add volume 2's ~30 additional stories with a second
anchor-extraction path.

Story extraction stops each tale at the following `<h3>REMARQUES</h3>` -
the scholarly comparative commentary that follows every story here is
deliberately excluded from what gets read aloud, not just the next
story's heading.

## Languages

The provider always loads, and decides **per search** whether to answer:
a search made in French gets an answer, any other language gets none.
The language of a search is the pipeline plugin's `lang` field, else the
language of the session the search came from, else (an older plugin
sends neither) the device's own language. That matters on a HiveMind
hub, where one ovos-core serves many users at once, each session in its
own language: a French session must get these stories on a hub whose own
language is English, and an English session must not get French ones. A
`ping` that names a language (the same way) only gets a pong when that
is French. Fetching a story is never gated on language - it is addressed
to this provider directly.

## Title matching

The book prints every title in capitals (*LA BICHE BLANCHE*). Titles
match regardless of case, accents, punctuation, `&` (read as "et") and
a leading article, so "la biche blanche", "biche blanche" and "l'oiseau
de verite" all find their story at full confidence; the part before a
title's first comma counts too, slightly below the whole title ("la
bourse"). The title that gets **spoken** is in ordinary case - *La Biche
Blanche*, *Le Roi d'Angleterre et son Filleul* - since a TTS engine may
spell capitals out letter by letter; `content_id` stays the index's own
capitalised title. A search that names no title at all ("raconte-moi
une histoire") gets one random story at confidence 0.9, or 1.0 when it
named this collection.

## Collection hints

Responds to `collection_hint` values like "cosquin", "lorraine",
"lorraine tales", "contes de lorraine", "emmanuel cosquin", matched
fuzzily (see `COLLECTION_ALIASES` in `__init__.py`).

## Content type

Identifies as `content_type: "story"` or `"tale"`. A search with a
`content_type` hint for anything else gets no response from this
provider.

## Credits

Content sourced from [Project Gutenberg](https://www.gutenberg.org/).
Scraping/extraction/caching logic ported from
[ovos-skill-andrew-lang-tales](https://github.com/andlo/ovos-skill-andrew-lang-tales)
and [ovos-skill-bechstein-tales](https://github.com/andlo/ovos-skill-bechstein-tales).

## Category
**Entertainment**

## Tags
#stories #fairytales #folklore #cosquin #lorraine #french #provider

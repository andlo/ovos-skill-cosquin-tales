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
> French. **On any device language other than French, this provider
> never loads at all**: `initialize()` checks the device's language
> against `SUPPORTED_LANGUAGES = {"fr"}` before loading the index or
> registering any bus events, logging why. Set your OVOS device's
> language to French (`fr-*`) to use this provider.

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

"""Tests for extract_book() - includes a regression case for the key
structural decision found while building this: each story's paragraphs
must stop at the 'REMARQUES' (<h3>) scholarly commentary that follows
every tale, not just at the next story's <h2>. test_text_cleanup.py runs
it on a cut-down real page."""
import json
from pathlib import Path

from conftest import extract_book

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
""".encode("utf-8")


def test_extract_book_stops_before_remarques():
    stories, errors = extract_book(SAMPLE_HTML, ["I", "II"])

    assert errors == {}
    assert stories["I"] == ["Il était une fois un bûcheron.", "Il devint fort et brave."]
    assert "plusieurs provinces" not in " ".join(stories["I"])


def test_extract_book_second_story():
    stories, _ = extract_book(SAMPLE_HTML, ["I", "II"])

    assert stories["II"] == ["Il y avait une princesse changée en biche."]


def test_extract_book_missing_anchor_is_an_error_for_that_story_only():
    stories, errors = extract_book(SAMPLE_HTML, ["II", "XCIX"])

    assert list(stories) == ["II"]
    assert "XCIX" in errors["XCIX"]


def test_the_index_points_at_the_page_itself_not_a_redirect():
    """/ebooks/57892.html.images answered 302, then 301, then the page:
    three requests for one book."""
    index = json.loads((Path(__file__).resolve().parents[1] / "locale" / "fr-fr" / "index.json")
                       .read_text(encoding="utf-8"))
    assert {e["url"] for e in index.values()} == {
        "https://www.gutenberg.org/cache/epub/57892/pg57892-images.html"}

"""What a story reads like once extracted, on the real page from
gutenberg.org cut down to four stories (tests/fixtures/). Each test
names what the old extractor did with the same page."""
from conftest import extract_book, fixture_page

ANCHORS = ["I", "XVIII", "XXI", "XXIX"]


def story(anchor):
    stories, errors = extract_book(fixture_page("contes-de-lorraine.html"), ANCHORS)
    assert anchor in stories, errors
    return stories[anchor]


def test_a_page_number_in_a_sentence_is_not_read():
    """'un jour, il donna à l'un de ses camarades[p. 2]un tel coup de poing'."""
    assert story("I")[0] == (
        "On envoya le petit garçon à l'école; il était très méchant et d'une force extraordinaire: "
        "un jour, il donna à l'un de ses camarades un tel coup de poing que tous les écoliers furent "
        "lancés à l'autre bout du banc. Le maître d'école lui ayant fait des reproches, Jean le jeta "
        "par la fenêtre. Après cet exploit, il fut renvoyé de l'école, et son père lui dit: «Il est "
        "temps d'aller faire ton tour d'apprentissage.»")


def test_a_page_number_on_its_own_is_not_a_paragraph():
    """LA BICHE BLANCHE used to end on a paragraph reading '[p. 234]'."""
    paragraphs = story("XXI")
    assert paragraphs[-1].endswith("Le roi fit mourir la méchante sorcière et vécut heureux avec sa femme.")
    assert not any("[p." in p for p in paragraphs)


def test_the_song_is_read_line_by_line():
    """The white doe's song is <div class="verse">, not <p>, and was never
    read: the tale went from 'La nuit, la vraie reine revint:' straight to
    'Les serviteurs entendirent tout'."""
    paragraphs = story("XXI")
    song = paragraphs.index("La nuit, la vraie reine revint:") + 1
    assert paragraphs[song] == (
        "«Bichaudelle, ouvre-moi ta porte.\n—Plaît-il, dame?—Où est le roi?\n"
        "Le roi est-il couché?—Oui, dame, il est au chevet,\nQui tient sa dame par la main.\n"
        "—Hélas! plus que deux nuits, mon cher fils,\nEt si le roi ton père ne me délivre,\n"
        "Je serai donc toute ma vie biche blanche au bois!»")
    assert paragraphs[song + 1] == "Les serviteurs entendirent tout, mais ils n'osèrent rien dire."


def test_the_remarques_are_still_not_read():
    assert not any("Cavallius" in p for p in story("XXI"))


def test_footnote_numbers_are_not_read_and_words_stay_apart():
    """'Un jour, la pouillotte[255]et le coucherillot[256]s'en allèrent'."""
    paragraphs = story("XXIX")
    assert paragraphs[0].startswith("Un jour, la pouillotte et le coucherillot s'en allèrent aux noisettes.")
    assert "qui étrangle en grand gosillot.—Tu n'en n'auras pas" in paragraphs[1]


def test_peuil_et_punce_is_read_in_french_only():
    """The tale is printed twice, side by side, in the Lorraine dialect and
    in French, and both were read one paragraph after the other."""
    paragraphs = story("XVIII")
    assert paragraphs[0].startswith("Un jour, Pou et Puce voulurent aller glaner.")
    assert not any("Peuil" in p or "Punce" in p for p in paragraphs)
    # its cumulative rhyme keeps its line breaks
    assert "—«Puce est croquée.\n«Volet bat.\n«Coq chante.»" in paragraphs

"""The AI's cards as plain text (notosaurus_core.cards.plain): a tag or Markdown the AI
wrote despite its rules would show as it is in Anki (every field is escaped)."""

import asyncio

from notosaurus_core import cards, llm
from notosaurus_core.config import AIConfig
from notosaurus_core.models import Card, Deck, Revision


def test_emphasis_becomes_brackets_and_tags_go():
    assert cards.plain('Quel est le son de voyelle dans "tiger" (a t<u>i</u>ger) ?') == (
        'Quel est le son de voyelle dans "tiger" (a t[i]ger) ?'
    )
    assert cards.plain("le <b>chat</b> et le <strong>chien</strong>") == "le [chat] et le [chien]"
    assert cards.plain("<i>Ser</i> ou <em>estar</em> ?") == "[Ser] ou [estar] ?"
    assert cards.plain('<mark class="x">1789</mark>') == "[1789]"
    assert cards.plain("un **mot** en __gras__") == "un [mot] en __gras__"  # "__" belongs to words (__init__)
    assert cards.plain("<b>a <u>b</u></b>") == "[a [b]]"  # nested, inside out
    assert cards.plain("ligne 1<br>ligne 2<br/>ligne 3") == "ligne 1\nligne 2\nligne 3"
    assert cards.plain("<p>un</p><p>deux</p>") == "un\ndeux"
    assert cards.plain('<span style="color:red">rouge</span>') == "rouge"  # other tags: gone, their text kept


def test_what_isnt_markup_is_kept():
    for text in (
        "a < b et b > c",  # a comparison, not a tag
        "3 * 4 = 12, 2*x",  # a product, not Markdown
        "\\(a^2 + b^2\\)",  # MathJax
        "La Révolution commence en {{c1::1789}}.",  # a gap
        "snake_case et __init__",  # underscores in words: not emphasis (no text between a pair)
        "",
    ):
        assert cards.plain(text) == text, text


def test_every_text_of_a_card_choices_too():
    card = Card(
        front="<u>a</u>", back="**b**", info="<i>c</i>", choices=["<b>x</b>", "y"],
        fun_fact="<em>d</em>", explanation="<b>e</b>", mnemonic="<u>f</u>", picture_prompt="<b>kept</b>",
    )  # fmt: skip
    cards.plain_cards([card])
    assert (card.front, card.back, card.info, card.choices) == ("[a]", "[b]", "[c]", ["[x]", "y"])
    assert (card.fun_fact, card.explanation, card.mnemonic) == ("[d]", "[e]", "[f]")
    assert card.picture_prompt == "<b>kept</b>"  # not a card text (never shown)


def test_extraction_and_revision_come_out_plain(monkeypatch):
    async def answer(s, images, text, schema, *args, **kwargs):
        # The schema the AI fills (its own Card model), as JSON: a revision has a summary
        if "summary" in schema.model_fields:
            return schema.model_validate({"deck": "D", "cards": [{"front": "**x**", "back": "y"}], "summary": "s"})
        return schema.model_validate({"deck": "D", "cards": [{"front": "t<u>i</u>ger", "back": "<b>i</b>"}]})

    monkeypatch.setattr(llm, "_ask_provider", answer)
    s = AIConfig(llm="gemini", gemini_api_key="k")
    found = asyncio.run(llm.extract_cards(s, [], "p"))
    assert (found.deck.cards[0].front, found.deck.cards[0].back) == ("t[i]ger", "[i]")
    revised = asyncio.run(llm.revise_cards(s, [], "p", Deck(deck="D", cards=[Card(front="a", back="b")]), "fix"))
    assert isinstance(revised, Revision) and revised.cards[0].front == "[x]"

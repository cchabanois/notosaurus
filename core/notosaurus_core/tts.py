"""Card audio, generated with edge-tts (free Microsoft neural voices).

Each mp3 is named after the text plus a hash of (voice, rate, text), e.g.
"la-madre-3f2a1c9e.mp3". Card audio lives in the lesson's audio/ folder;
previews go to the cache (files.py, tts/) and are reused when the lesson is exported.

A card may have a voice of its own (Card.voice), else it is the lesson's: a lesson moved
from the phone keeps its sounds, made with the relay's voices, the names being the same on
both (Speech.kt, core/shared-cases.json sound_file). card_voice says which one a sound is in.

`rate`: the speed, e.g. "-10%" (slightly slower, for learners).
"""

import asyncio
import hashlib
import logging
import os
import re
import shutil
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import edge_tts

from . import files
from .cards import BLANK, GAP, is_choice, is_cloze
from .errors import loggable
from .models import Card

log = logging.getLogger("notosaurus")

MAX_PARALLEL = 4

# "es_ES": {{tts}} tag read by Anki itself; "es-ES-ElviraNeural": edge-tts mp3.
ANKI_LOCALE = re.compile(r"^[a-z]{2,3}_[A-Z]{2}$")

_voices: list[dict] | None = None


def cache_dir() -> Path:
    path = files.cache_dir("tts")
    path.mkdir(parents=True, exist_ok=True)
    return path


MATH = re.compile(r"\\\(|\\\[")  # MathJax: \( … \) or \[ … \]


def has_math(text: str) -> bool:
    """A formula (MathJax) in the text: not read aloud (a voice would read the code)."""
    return bool(MATH.search(text))


# What a sentence with a blank (cards.BLANK: "Le chat boit du …") says in brackets
BRACKETS = re.compile(r"\s*\([^)]*\)")
# A phonetic transcription, between slashes or square brackets ("/ɜː/", "[ˈtaɪɡə]"): a voice
# would read the slashes and guess at the symbols. Between slashes: no space, no digit (a
# date, "km/h" stay); between square brackets: with a phonetic symbol (IPA letters, length
# and stress marks, diacritics, æ ø œ θ ð), since brackets also single a part out ("t[i]ger")
PHONETIC = r"ɐ-ʯʰ-˿̀-ͯæøœθð"
TRANSCRIPTION = re.compile(
    rf"(?<![\w/])/[^/\s\d]{{1,24}}/(?![\w/])|\[[^\[\]\s\d]{{0,24}}[{PHONETIC}][^\[\]\s\d]{{0,24}}\]"
)
MARKED = re.compile(r"\[([^\[\]\n]{1,40})\]")  # a part singled out ("t[i]ger"): read as the word
QUOTED = re.compile(r"[“\"«]\s*([^”\"»\n]{1,60}?)\s*[”\"»]|‘([^’\n]{1,60}?)’")  # the front's examples
LETTER = re.compile(r"[^\W_]")  # a letter or a digit: something a voice says ("$1" is read)


def speakable(text: str) -> str:
    """The text as a voice can read it: transcriptions out, a part singled out in brackets
    read as its word."""
    text = TRANSCRIPTION.sub(" ", text)
    text = MARKED.sub(lambda m: m.group(1), text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def spoken(card: Card, dictation: bool = False) -> str:
    """What a card's sound says: its back, as a voice can read it (speakable). A back that
    is only a transcription ("/ɜː/"): the examples quoted on the front, the only way to hear
    the sound ("bird"), each read on its own; none: nothing. A dictation's card whose front
    is a sentence with a blank: the sentence with the word, then the word (alone, "vers"
    could be "verre" or "vert"); each on its line, read on its own (lines). A front that is
    the blank alone ("…", cards.DICTATION_FRONT): the word, once."""
    back = speakable(card.back.strip())
    if not LETTER.search(back):
        examples = [speakable(a or b) for a, b in QUOTED.findall(card.front)]
        return "\n".join(e for e in examples if LETTER.search(e))
    sentence = BRACKETS.sub("", card.front).strip()
    if not dictation or "\n" in back or not BLANK.search(sentence):
        return back
    said = BLANK.sub(lambda _: back, sentence, count=1)
    if said == back:
        return back
    return f"{said}{'' if said[-1] in '.!?' else '.'}\n{back}"


def sound_sides(card: Card) -> tuple[bool, bool]:
    """Which of the card's sides are read aloud (Card.sound): (front, back). Empty: as before
    the choice, its back, not a text with gaps' nor a multiple choice's (their back was only an
    extra, their options read). Never a side with a formula (the voice would read its code)."""
    front, back = {"back": (False, True), "front": (True, False), "both": (True, True), "none": (False, False)}.get(
        card.sound, (False, not is_cloze(card.front) and not is_choice(card))
    )
    return front and not has_math(card.front), back and not has_math(card.back)


def spoken_front(card: Card) -> str:
    """What a card's front says, read aloud: its question as it shows, as a voice can read it
    (speakable). A text with gaps: the whole text, as a dictation (the words heard, written in
    the gaps): its blanks read as silences sounded like words left out, and the same sound for
    each of its cards (a gap each, the others shown)."""
    if GAP.search(card.front):
        return spoken_cloze_back(card)
    front = speakable(BRACKETS.sub("", card.front.strip()))
    return front if LETTER.search(front) else ""


def spoken_cloze_back(card: Card) -> str:
    """What a text with gaps says on its answer: the whole text, each gap its answer."""
    said = speakable(GAP.sub(lambda m: m.group(1), card.front.strip()))
    return said if LETTER.search(said) else ""


def lines(text: str) -> list[str]:
    """What is read on its own, then joined: each line of a text. A natural voice given a
    lone word then a sentence in one text makes up words (Chirp 3 HD: "vers. Les bras
    tendus vers lui…" came out twice as long, with words of its own)."""
    return [line.strip()[:MAX_LINE] for line in text.splitlines() if line.strip()]


def spoken_sides(card: Card, dictation: bool = False) -> tuple[str, str]:
    """What each of the card's sides says read aloud (sound_sides), "" for a side not read:
    its front as it shows (spoken_front); its back, a text with gaps' the whole text
    (spoken_cloze_back), another card's its answer (spoken). With the lesson's dictation, a
    plain card's back always: its dictation card is heard (a transcription with no example to
    read: nothing)."""
    front, back = sound_sides(card)
    plain = not is_cloze(card.front) and not is_choice(card)
    if dictation and plain:
        back = not has_math(card.back)
    said_front = spoken_front(card) if front and card.front.strip() else ""
    if not back or not card.front.strip():
        return said_front, ""
    if is_cloze(card.front):
        return said_front, spoken_cloze_back(card)
    return said_front, spoken(card, dictation) if card.back.strip() else ""


def spoken_backs(cards: list[Card], dictation: bool = False) -> list[str]:
    """What the cards' sounds say, each side's (spoken_sides): none for a side not read, a
    formula (the voice would read the MathJax code), a transcription with no example."""
    return [text for _, text in _speaking(cards, dictation)]


def _speaking(cards: list[Card], dictation: bool) -> list[tuple[Card, str]]:
    return [(c, text) for c in cards for text in spoken_sides(c, dictation) if text]


def spoken_voices(
    cards: list[Card], lesson_voice: str, directory: Path | None, rate: str, dictation: bool = False
) -> dict[str, str]:
    """{what a card's sound says (spoken_backs): the voice it is in (card_voice)}."""
    return {text: card_voice(c, lesson_voice, text, directory, rate) for c, text in _speaking(cards, dictation)}


def is_anki_locale(voice: str) -> bool:
    return bool(ANKI_LOCALE.match(voice))


RATE = "-10%"
NORMAL = "+0%"  # not slowed
MAX_LINE = 200  # characters read of a line: a back's sound, not a text read out


def is_edge_voice(voice: str) -> bool:
    """A voice this computer reads with (edge-tts: "es-ES-ElviraNeural")."""
    return voice.endswith("Neural")


def card_voice(card: Card, lesson_voice: str, text: str, directory: Path | None, rate: str = RATE) -> str:
    """The voice of the card's sound: its own (Card.voice) when this computer can read with it
    or its sound is there already (made on the phone), else the lesson's."""
    own = card.voice
    if not own or own == lesson_voice:
        return lesson_voice
    if is_edge_voice(own) or (directory is not None and (directory / filename(text, own, rate)).is_file()):
        return own
    return lesson_voice


def filename(text: str, voice: str, rate: str = RATE) -> str:
    # Anki keeps all media in one folder: the hash keeps names unique across
    # voices, rates and lessons, the slug keeps them readable.
    digest = hashlib.sha1(f"{voice}|{rate}|{text}".encode()).hexdigest()[:8]
    return f"{files.slugify(text, 30) or 'audio'}-{digest}.mp3"


async def _synthesize(text: str, voice: str, path: Path, rate: str) -> None:
    tmp = path.with_suffix(".part")
    try:
        await edge_tts.Communicate(text, voice, rate=rate).save(str(tmp))
    except BaseException:  # failed or stopped (sounds made ahead, replaced): nothing left behind
        tmp.unlink(missing_ok=True)
        raise
    tmp.rename(path)  # never leave a half-written mp3 behind


async def tts(text: str, voice: str, directory: Path | None = None, rate: str = RATE) -> Path:
    """mp3 of `text` in `directory` (default: preview cache), synthesized if missing."""
    name = filename(text, voice, rate)
    path = (directory or cache_dir()) / name
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    cached = cache_dir() / name
    if directory and cached.exists():
        shutil.copyfile(cached, path)
    else:
        await _synthesize_lines(text, voice, path, rate)
    return path


async def _synthesize_lines(text: str, voice: str, path: Path, rate: str) -> None:
    """Each line (lines) read on its own, the mp3s joined (MPEG frames follow each other)."""
    said = lines(text)
    if len(said) <= 1:
        await _synthesize(said[0] if said else text, voice, path, rate)
        return
    parts = [path.with_name(f"{path.stem}.{i}.mp3") for i in range(len(said))]
    try:
        for line, part in zip(said, parts, strict=True):
            await _synthesize(line, voice, part, rate)
        tmp = path.with_suffix(".joined")
        with tmp.open("wb") as f:
            f.write(b"".join(part.read_bytes() for part in parts))
            f.flush()
            os.fsync(f.fileno())  # on the disk before its rename: never an empty mp3 after a crash
        tmp.rename(path)
    finally:
        for part in parts:
            part.unlink(missing_ok=True)


async def tts_many(
    texts: list[str],
    voice: str,
    directory: Path,
    rate: str = RATE,
    on_done: Callable[[], None] | None = None,
) -> tuple[dict[str, Path], int]:
    """Audio for every text in `directory`. Returns {text: mp3} and the number of failures.
    `on_done`: told as each different text is done (made, found or failed), for a progress."""
    sem = asyncio.Semaphore(MAX_PARALLEL)

    async def one(text: str) -> tuple[str, Path | None]:
        async with sem:
            try:
                return text, await tts(text, voice, directory, rate)
            except Exception as e:  # network, unknown voice…: the card goes out without sound
                # Never the text (no lesson in logs), nor the message (it may quote it)
                log.warning("TTS %s failed (%d characters): %s", voice, len(text), loggable(e))
                return text, None
            finally:
                if on_done:
                    on_done()

    results = await asyncio.gather(*(one(t) for t in dict.fromkeys(texts)))
    audio = {t: p for t, p in results if p}
    return audio, len(results) - len(audio)


async def tts_voices(
    voices: Mapping[str, str], directory: Path, rate: str = RATE, on_done: Callable[[], None] | None = None
) -> tuple[dict[str, Path], int]:
    """tts_many for texts each in its own voice ({text: voice}, spoken_voices)."""
    audio, failures = {}, 0
    for voice in dict.fromkeys(voices.values()):
        made, failed = await tts_many([t for t, v in voices.items() if v == voice], voice, directory, rate, on_done)
        audio, failures = {**audio, **made}, failures + failed
    return audio, failures


def prune(directory: Path, keep: set[Path]) -> None:
    """Delete mp3s no card uses any more (edited backs, changed voice)."""
    for mp3 in directory.glob("*.mp3"):
        if mp3 not in keep:
            mp3.unlink()


# A natural voice per language, for prompts whose voice is "auto"
PREFERRED = {
    "es": "es-ES-ElviraNeural",
    "es-mx": "es-MX-DaliaNeural",
    "en": "en-GB-SoniaNeural",
    "en-us": "en-US-JennyNeural",
    "de": "de-DE-KatjaNeural",
    "it": "it-IT-ElsaNeural",
    "fr": "fr-FR-DeniseNeural",
    "pt": "pt-PT-RaquelNeural",
    "pt-br": "pt-BR-FranciscaNeural",
    "nl": "nl-NL-ColetteNeural",
}


# A language's usual variety, when it is asked alone: "en" is British English, not the first
# English voice by name (en-AU); "cmn" (the relay's name of Mandarin) China's. Else "es-es",
# "de-de"… (Speech.VARIETY on the phone)
USUAL = {"en": "en-gb", "pt": "pt-pt", "cmn": "cmn-cn"}
# The relay's voice for a language (Chirp 3 HD: the same name in every language), its
# preferred one as PREFERRED are edge-tts's (Speech.DEFAULT_VOICE on the phone)
RELAY_VOICE = "Aoede"


def voice_tag(language: str) -> str:
    """A language as the relay's voices name it (lowercase): Chinese, which the AI calls "zh"
    (zh-CN, zh-Hant, zh-HK…), under the spoken language's name, Mandarin "cmn-cn" or "cmn-tw",
    Cantonese "yue-hk" (Hong Kong's, Macao's); any other as it is (Speech.voiceTag)."""
    tag = language.strip().replace("_", "-").lower()
    parts = tag.split("-")
    if parts[0] != "zh":
        return tag
    region = next((p for p in parts[1:] if len(p) == 2), None)
    if "yue" in parts or region in ("hk", "mo"):
        return "yue-hk"
    if region == "tw" or "hant" in parts:
        return "cmn-tw"
    return f"cmn-{region}" if region else "cmn"


def pick_voice(language: str, available: Sequence[Mapping[str, str]], chosen: Mapping[str, str] | None = None) -> str:
    """The voice for a language ("es-ES", "en", "pt-BR"…) among `available` (edge-tts's, or
    the relay's on the phone: {"voice", "locale", "gender"}): the one the user chose for that
    variety (`chosen`, by locale; for a language alone, the one chosen for one of its
    varieties, the first by locale), else one of that language's voices: of that variety
    first, else of its usual one (USUAL), its preferred voice first (PREFERRED, RELAY_VOICE),
    else a female one, else the first by name; "" when there is none. Chinese found under the
    relay's names too (voice_tag). The one rule of the computer and the phone (Speech.pick,
    core/shared-cases.json voice_for)."""
    tag = language.strip().replace("_", "-").lower()
    if not tag:
        return ""
    mine = {locale.lower(): voice for locale, voice in (chosen or {}).items() if voice}
    for asked in dict.fromkeys((tag, voice_tag(tag))):
        if asked in mine:
            return mine[asked]
        base = asked.split("-")[0]
        if asked == base and (same := [v for locale, v in sorted(mine.items()) if locale.split("-")[0] == base]):
            return same[0]

    def language_of(voice: Mapping[str, str]) -> str:
        return voice["locale"].lower().split("-")[0]

    if not any(language_of(v) == tag.split("-")[0] for v in available):
        tag = voice_tag(tag)  # the relay's name of it
    base = tag.split("-")[0]
    usual = USUAL.get(base, f"{base}-{base}")
    preferred = set(PREFERRED.values())

    def rank(voice: Mapping[str, str]) -> tuple:
        locale, name = voice["locale"].lower(), voice["voice"]
        favourite = name in preferred or name.endswith(f"-{RELAY_VOICE}")
        return (locale != tag, locale != usual, not favourite, voice.get("gender") != "Female", name)

    found = [v for v in available if language_of(v) == base]
    return min(found, key=rank)["voice"] if found else ""


async def voice_for(language: str, chosen: Mapping[str, str] | None = None) -> str:
    """The voice for a language ("es-ES", "en", "pt-BR"…) among edge-tts's (pick_voice): the
    one the user chose, else the preferred voice of that variety without asking edge-tts
    (it has them all), else as pick_voice finds it in edge-tts's list; edge-tts unreachable:
    the preferred voice of that variety, else of the language; "" when there is none."""
    tag = language.strip().replace("_", "-").lower()
    if not tag:
        return ""
    if mine := pick_voice(tag, [], chosen):
        return mine
    base = tag.split("-")[0]
    preferred = PREFERRED.get(tag) or PREFERRED.get(base, "")
    if preferred.lower().startswith(tag):  # "es-ES" → es-ES-ElviraNeural, "es" → es-ES-ElviraNeural
        return preferred
    try:
        available = await voices()
    except Exception:  # no network: only the preferred ones
        return preferred
    return pick_voice(tag, available, chosen)


async def voices() -> list[dict]:
    """Available voices (short name, locale, gender), cached in memory."""
    global _voices
    if _voices is None:
        _voices = sorted(
            (
                {"voice": v["ShortName"], "locale": v["Locale"], "gender": v["Gender"]}
                for v in await edge_tts.list_voices()
            ),
            key=lambda v: v["voice"],
        )
    return _voices

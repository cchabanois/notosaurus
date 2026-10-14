"""Card audio, generated with edge-tts (free Microsoft neural voices).

Each mp3 is named after the text plus a hash of (voice, rate, text), e.g.
"la-madre-3f2a1c9e.mp3". Card audio lives in the lesson's audio/ folder;
previews go to the cache (files.py, tts/) and are reused when the lesson is exported.

`rate`: the speed, e.g. "-10%" (slightly slower, for learners).
"""

import asyncio
import hashlib
import logging
import re
import shutil
from collections.abc import Mapping
from pathlib import Path

import edge_tts

from . import files
from .cards import is_choice, is_cloze
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


# A sentence's blank for the word to write ("Le chat boit du …"), and what it says in brackets
BLANK = re.compile(r"…|\.{3}|_{3,}")
BRACKETS = re.compile(r"\s*\([^)]*\)")


def spoken(card: Card, dictation: bool = False) -> str:
    """What a card's sound says: its back. A dictation's card whose front is a sentence
    with a blank: the sentence with the word, then the word (alone, "vers" could be
    "verre" or "vert"); each on its line, read on its own (lines)."""
    back = card.back.strip()
    sentence = BRACKETS.sub("", card.front).strip()
    if not dictation or "\n" in back or not BLANK.search(sentence):
        return back
    said = BLANK.sub(lambda _: back, sentence, count=1)
    return f"{said}{'' if said[-1] in '.!?' else '.'}\n{back}"


def lines(text: str) -> list[str]:
    """What is read on its own, then joined: each line of a text. A natural voice given a
    lone word then a sentence in one text makes up words (Chirp 3 HD: "vers. Les bras
    tendus vers lui…" came out twice as long, with words of its own)."""
    return [line.strip()[:MAX_LINE] for line in text.splitlines() if line.strip()]


def spoken_backs(cards: list[Card], dictation: bool = False) -> list[str]:
    """What the cards' sounds say (spoken). None for: a back with a formula (the voice
    would read the MathJax code), a text with gaps (its back is only an extra), a multiple
    choice (the options are read)."""
    return [
        spoken(c, dictation)
        for c in cards
        if c.front.strip() and c.back.strip() and not has_math(c.back) and not is_cloze(c.front) and not is_choice(c)
    ]


def is_anki_locale(voice: str) -> bool:
    return bool(ANKI_LOCALE.match(voice))


RATE = "-10%"
NORMAL = "+0%"  # not slowed
MAX_LINE = 200  # characters read of a line: a back's sound, not a text read out


def filename(text: str, voice: str, rate: str = RATE) -> str:
    # Anki keeps all media in one folder: the hash keeps names unique across
    # voices, rates and lessons, the slug keeps them readable.
    digest = hashlib.sha1(f"{voice}|{rate}|{text}".encode()).hexdigest()[:8]
    return f"{files.slugify(text, 30) or 'audio'}-{digest}.mp3"


async def _synthesize(text: str, voice: str, path: Path, rate: str) -> None:
    tmp = path.with_suffix(".part")
    await edge_tts.Communicate(text, voice, rate=rate).save(str(tmp))
    tmp.rename(path)  # never leave a half-written mp3 behind


async def tts(text: str, voice: str, directory: Path | None = None, rate: str = RATE) -> Path:
    """mp3 of `text` in `directory` (default: preview cache), synthesized if missing."""
    name = filename(text, voice, rate)
    path = (directory or cache_dir()) / name
    if not path.exists():
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
        tmp.write_bytes(b"".join(part.read_bytes() for part in parts))
        tmp.rename(path)
    finally:
        for part in parts:
            part.unlink(missing_ok=True)


async def tts_many(texts: list[str], voice: str, directory: Path, rate: str = RATE) -> tuple[dict[str, Path], int]:
    """Audio for every text in `directory`. Returns {text: mp3} and the number of failures."""
    sem = asyncio.Semaphore(MAX_PARALLEL)

    async def one(text: str) -> tuple[str, Path | None]:
        async with sem:
            try:
                return text, await tts(text, voice, directory, rate)
            except Exception as e:  # network, unknown voice…: the card goes out without sound
                # Never the text (no lesson in logs), nor the message (it may quote it)
                log.warning("TTS %s failed (%d characters): %s", voice, len(text), loggable(e))
                return text, None

    results = await asyncio.gather(*(one(t) for t in dict.fromkeys(texts)))
    audio = {t: p for t, p in results if p}
    return audio, len(results) - len(audio)


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


async def voice_for(language: str, chosen: Mapping[str, str] | None = None) -> str:
    """The voice for a language ("es-ES", "en", "pt-BR"…): the one the user chose for that
    variety (`chosen`, by locale; for a language alone, the one chosen for one of its
    varieties), else the preferred voice of that variety, else one of its voices (a female
    one first), else the preferred voice of the language, else any of its voices; "" when
    there is none."""
    tag = language.strip().replace("_", "-").lower()
    if not tag:
        return ""
    base = tag.split("-")[0]
    mine = {locale.lower(): voice for locale, voice in (chosen or {}).items() if voice}
    if tag in mine:
        return mine[tag]
    if tag == base and (same := [v for locale, v in sorted(mine.items()) if locale.split("-")[0] == base]):
        return same[0]
    preferred = PREFERRED.get(tag) or PREFERRED.get(base, "")
    if preferred.lower().startswith(tag):  # "es-ES" → es-ES-ElviraNeural, "es" → es-ES-ElviraNeural
        return preferred
    try:
        available = await voices()
    except Exception:  # no network: only the preferred ones
        available = []

    def first(found: list[dict]) -> str:
        return sorted(found, key=lambda v: (v["gender"] != "Female", v["voice"]))[0]["voice"] if found else ""

    return (
        first([v for v in available if v["locale"].lower() == tag])
        or preferred
        or first([v for v in available if v["locale"].lower().split("-")[0] == base])
    )


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

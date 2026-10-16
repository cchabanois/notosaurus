"""Send notes straight into Anki desktop through the AnkiConnect add-on.

https://foosoft.net/projects/anki-connect/ — Anki must be running with the add-on
installed. Notes already sent are updated (same note type, deck and front) instead
of duplicated, and moved first when the lesson's deck (or a card's part) changed;
notes deleted in Notosaurus are left untouched in Anki.
"""

import base64
import html
import re
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field

import httpx

from . import settings
from .anki import TAG_PREFIX, Note, family, guids, model_id
from .errors import AppError

TIMEOUT = 30.0
_transport: httpx.AsyncBaseTransport | None = None  # tests plug a fake AnkiConnect here


class AnkiConnectError(AppError):
    status = 502


# Messages from AnkiConnect / the Notosaurus bridge that have their own error code.
KNOWN_ERRORS = {
    "auth not configured": "anki.sync_not_logged_in",
    "no profile open": "anki.no_profile",
}


@dataclass
class SendResult:
    added: int
    updated: int
    synced: bool
    sync_error: dict | None = None  # {"code", "params"}, translated by the page
    sync_skipped: bool = False  # the profile isn't logged in to AnkiWeb: not tried
    converted: int = 0  # of the updated notes, those moved to another note type (options changed)
    moved: int = 0  # of the updated notes, those moved to another deck (the lesson's deck changed)
    note_ids: dict[str, int] = field(default_factory=dict)  # card id → its note: kept with the lesson
    conversion_unsupported: bool = False  # AnkiConnect too old to change a note's type: added instead
    note_types_updated: int = 0  # made by an older Notosaurus: brought up to date
    restructured: list[str] = field(default_factory=list)  # a field or card added: Anki asks for a full sync


async def _invoke(client: httpx.AsyncClient, action: str, **params):
    s = settings.current()
    body = {"action": action, "version": 6, "params": params}
    if s.ankiconnect_key:
        body["key"] = s.ankiconnect_key
    try:
        response = await client.post(s.ankiconnect_url, json=body)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as e:
        raise AnkiConnectError("anki.unreachable") from e
    except ValueError as e:
        raise AnkiConnectError("anki.bad_response") from e
    if error := data.get("error"):
        code = next((c for text, c in KNOWN_ERRORS.items() if text in str(error)), "anki.error")
        raise AnkiConnectError(code, action=action, detail=str(error))
    return data.get("result")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT, transport=_transport)


async def tag_notes(add: dict[str, set[int]], remove: dict[str, set[int]]) -> None:
    """Tags put on notes and taken off others ({tag: note ids}): a test's tag following
    its lessons (exams.retagging). Notes gone from Anki are skipped by AnkiConnect."""
    async with _client() as client:
        for tag, ids in remove.items():
            if ids:
                await _invoke(client, "removeTags", notes=sorted(ids), tags=tag)
        for tag, ids in add.items():
            if ids:
                await _invoke(client, "addTags", notes=sorted(ids), tags=tag)


async def active_profile() -> str | None:
    """Anki profile open right now, or None (Anki closed, profile screen, old AnkiConnect)."""
    try:
        async with httpx.AsyncClient(timeout=2.0, transport=_transport) as client:
            return await _invoke(client, "getActiveProfile") or None
    except AnkiConnectError:
        return None


async def sync_configured() -> bool | None:
    """Whether the open profile is logged in to AnkiWeb. The add-on's bridge knows;
    AnkiConnect has no such action: None (unknown)."""
    try:
        async with httpx.AsyncClient(timeout=2.0, transport=_transport) as client:
            result = await _invoke(client, "isSyncConfigured")
    except AnkiConnectError:
        return None
    return result if isinstance(result, bool) else None


async def profiles() -> list[str] | None:
    """Every Anki profile, or None when Anki can't be reached."""
    try:
        async with httpx.AsyncClient(timeout=2.0, transport=_transport) as client:
            return list(await _invoke(client, "getProfiles") or [])
    except AnkiConnectError:
        return None


async def deck_names() -> list[str] | None:
    """The open profile's decks, or None when Anki can't be reached."""
    try:
        async with httpx.AsyncClient(timeout=2.0, transport=_transport) as client:
            return list(await _invoke(client, "deckNames") or [])
    except AnkiConnectError:
        return None


async def version() -> int:
    async with _client() as client:
        return await _invoke(client, "version")


def same_as_packages(extra: dict) -> dict:
    """The note type's id and the notes' GUIDs of the .apkg, for the add-on's bridge: a
    package imported after a direct send (or the other way round) then updates the same
    note types and notes instead of adding them twice. AnkiConnect can't take them (an
    unknown parameter is an error): with it, use one way per profile."""
    return extra if settings.embedded() else {}


async def send(notes: list[Note], sent_before: dict[str, int] | None = None) -> SendResult:
    """`sent_before`: the lesson's notes from its last send, by card id: a card whose front was
    corrected updates its own note (history kept) instead of making another."""
    async with _client() as client:
        note_types = list(dict.fromkeys(n.nt for n in notes))
        known = await _invoke(client, "modelNames")
        await _create_note_types(client, [nt for nt in note_types if nt.name not in known])
        updated_types, restructured = await _bring_up_to_date(client, [nt for nt in note_types if nt.name in known])
        await _store_media(client, notes)
        moved, left = await _move_to_their_decks(client, notes)

        sending = _Sending(client, dict(zip(map(id, notes), guids(notes), strict=True)))
        sending.known = await _known_notes(client, notes, sent_before or {})
        for deck, nt in dict.fromkeys((n.deck, n.nt) for n in notes):
            await sending.send(deck, nt, [n for n in notes if (n.deck, n.nt) == (deck, nt)])
        for tag, ids in sending.retag.items():
            await _invoke(client, "addTags", notes=ids, tags=tag)
        await _drop_empty_decks(client, left - {n.deck for n in notes})

        result = SendResult(
            sending.added,
            sending.updated,
            synced=False,
            converted=sending.converted,
            moved=moved + sending.moved,
            note_ids=sending.sent,
            conversion_unsupported=sending.unsupported,
            note_types_updated=updated_types,
            restructured=restructured,
        )
        if not restructured:  # else Anki asks which side to keep: the user's choice, in Anki
            await _sync(client, result)
        return result


async def _move_to_their_decks(client: httpx.AsyncClient, notes: list[Note]) -> tuple[int, set[str]]:
    """The lesson's notes already in Anki (its tag) that are in another deck than where
    they go now (the lesson's deck, or a card's part, changed): their cards moved there,
    review history kept, so that the send updates them instead of adding them again.
    A note another lesson uses too stays. How many moved, and the decks they left."""
    tags = {t for n in notes for t in n.tags if t.startswith(TAG_PREFIX)}
    if len(tags) != 1:
        return 0, set()
    (tag,) = tags
    key_field = {n.nt.family: n.nt.key for n in notes}  # a note type's family: which field tells it
    target = {(n.nt.family, n.key): n.deck for n in notes}
    ids = await _invoke(client, "findNotes", query=f'"tag:{_search(tag)}"')
    infos = await _invoke(client, "notesInfo", notes=ids) if ids else []
    going: dict[int, str] = {}  # card id → its deck now
    for info in infos:
        if any(t.startswith(TAG_PREFIX) and t != tag for t in info["tags"]):
            continue
        kind = family(info["modelName"])
        deck = target.get((kind, info["fields"].get(key_field.get(kind, ""), {}).get("value")))
        going.update(dict.fromkeys(info.get("cards", []), deck) if deck else {})
    cards = await _invoke(client, "cardsInfo", cards=list(going)) if going else []
    moving = [c for c in cards if c["deckName"] != going[c["cardId"]]]
    for deck in dict.fromkeys(going[c["cardId"]] for c in moving):
        await _invoke(
            client, "changeDeck", cards=[c["cardId"] for c in moving if going[c["cardId"]] == deck], deck=deck
        )
    return len({c["note"] for c in moving}), {c["deckName"] for c in moving}


async def _known_notes(client: httpx.AsyncClient, notes: list[Note], known: dict[str, int]) -> dict[str, dict]:
    """The notes the cards had at their last send, still in Anki, by card id; with the
    decks their cards are in ("decks")."""
    ids = {n.card_id: known[n.card_id] for n in notes if n.card_id in known}
    infos = await _invoke(client, "notesInfo", notes=list(ids.values())) if ids else []
    found = {i["noteId"]: i for i in infos if i and i.get("noteId")}  # {} for a note deleted in Anki
    cards = [c for i in found.values() for c in i.get("cards", [])]
    for card in await _invoke(client, "cardsInfo", cards=cards) if cards else []:
        found[card["note"]].setdefault("decks", set()).add(card["deckName"])
    return {card: found[note] for card, note in ids.items() if note in found}


async def _create_note_types(client: httpx.AsyncClient, note_types: list) -> None:
    for nt in note_types:
        await _invoke(
            client,
            "createModel",
            modelName=nt.name,
            inOrderFields=list(nt.fields),
            css=nt.full_css,
            isCloze=nt.cloze,
            cardTemplates=[{"Name": t["name"], "Front": t["qfmt"], "Back": t["afmt"]} for t in nt.templates],
            **same_as_packages({"id": model_id(nt)}),
        )


async def _store_media(client: httpx.AsyncClient, notes: list[Note]) -> None:
    for path in dict.fromkeys(p for n in notes for p in n.media):
        await _invoke(client, "storeMediaFile", filename=path.name, data=base64.b64encode(path.read_bytes()).decode())


@dataclass
class _Sending:
    """The notes sent, one deck and note type at a time: each updates the note with its
    key, else takes over a note sent with other options, else is added."""

    client: httpx.AsyncClient
    guid_of: dict[int, str]  # id(note) → its GUID
    added: int = 0
    updated: int = 0
    converted: int = 0
    unsupported: bool = False
    retag: dict[str, list[int]] = field(default_factory=dict)  # notes sent before they had the lesson's tag
    others: dict[str, dict] = field(default_factory=dict)  # per deck: its notes of the other Notosaurus note types
    known: dict[str, dict] = field(default_factory=dict)  # card id → its note at the last send (_known_notes)
    sent: dict[str, int] = field(default_factory=dict)  # card id → its note now
    moved: int = 0  # known notes moved to the deck they go to now

    async def send(self, deck: str, nt, notes: list[Note]) -> None:
        existing = await self._existing(deck, nt)
        for note in notes:
            if await self._by_card(deck, nt, note, existing):
                continue
            if existing.get(note.key):
                await self._update(existing[note.key].pop(0), note)
            elif not await self._convert(deck, nt, note):
                await self._add(deck, nt, note)

    async def _existing(self, deck: str, nt) -> dict[str, list[int]]:
        """The deck's notes of this note type, by key; two cards with the same front
        ("le vol": vuelo, robo) have a note each."""
        # createDeck returns the id of the deck, existing or new. Searching by id
        # and comparing keys here avoids escaping names in Anki's search syntax.
        deck_id = await _invoke(self.client, "createDeck", deck=deck)
        ids = await _invoke(self.client, "findNotes", query=f'"note:{nt.name}" did:{deck_id}')
        infos = await _invoke(self.client, "notesInfo", notes=ids) if ids else []
        existing: dict[str, list[int]] = {}
        for info in infos:
            if nt.key in info["fields"]:
                existing.setdefault(info["fields"][nt.key]["value"], []).append(info["noteId"])
        return existing

    async def _by_card(self, deck: str, nt, note: Note, existing: dict[str, list[int]]) -> bool:
        """The card's own note from its last send (its front may have been corrected):
        updated there, moved to this deck if it was elsewhere, or moved to the new note
        type (options changed). False when it has none (deleted in Anki, never sent)."""
        info = self.known.pop(note.card_id, None)
        if not info or any(t.startswith(TAG_PREFIX) and t not in note.tags for t in info["tags"]):
            return False  # none, or another lesson's too: left where it is (as _move_to_their_decks)
        note_id = info["noteId"]
        if info["modelName"] == nt.name:
            await self._update(note_id, note)
        elif family(info["modelName"]) != nt.family or not await self._change_type(info, nt, note):
            return False
        for ids in existing.values():  # not taken again by a card with its front
            if note_id in ids:
                ids.remove(note_id)
        if info.get("cards") and info.get("decks", {deck}) != {deck}:
            await _invoke(self.client, "changeDeck", cards=info["cards"], deck=deck)
            self.moved += 1
        return True

    async def _change_type(self, old: dict, nt, note: Note) -> bool:
        """The note moved to the note type `nt` (options changed), its history kept;
        False with an AnkiConnect too old for it."""
        if self.unsupported:
            return False
        try:
            tags = sorted({*old["tags"], *note.tags})
            changed = {"id": old["noteId"], "modelName": nt.name, "fields": note.fields, "tags": tags}
            await _invoke(self.client, "updateNoteModel", note=changed)
        except AnkiConnectError as e:
            if not _unsupported(e):
                raise
            self.unsupported = True  # an old AnkiConnect: added next to it, as before
            return False
        self.sent[note.card_id] = old["noteId"]
        self.updated += 1
        self.converted += 1
        return True

    async def _update(self, note_id: int, note: Note) -> None:
        await _invoke(self.client, "updateNoteFields", note={"id": note_id, "fields": note.fields})
        for tag in (t for t in note.tags if t.startswith(TAG_PREFIX)):
            self.retag.setdefault(tag, []).append(note_id)
        self.sent[note.card_id] = note_id
        self.updated += 1

    async def _convert(self, deck: str, nt, note: Note) -> bool:
        """Sent before with other options (voice, reverse, typing, dictation): the same
        note moves to the new note type, keeping its review history."""
        if deck not in self.others:
            self.others[deck] = await _other_notosaurus_notes(self.client, deck)
        candidates = [i for i in self.others[deck].get((nt.family, nt.key, note.key), []) if i["modelName"] != nt.name]
        old = candidates[0] if candidates else None
        if not old or not await self._change_type(old, nt, note):
            return False
        self.others[deck][(nt.family, nt.key, note.key)].remove(old)
        return True

    async def _add(self, deck: str, nt, note: Note) -> None:
        self.sent[note.card_id] = await _invoke(
            self.client,
            "addNote",
            note={
                "deckName": deck,
                "modelName": nt.name,
                "fields": note.fields,
                "tags": note.tags,
                "options": {"allowDuplicate": True},  # same front in another deck is fine
                **same_as_packages({"guid": self.guid_of[id(note)]}),
            },
        )
        self.added += 1


def _unsupported(e: "AnkiConnectError") -> bool:
    return "unsupported action" in str(e.params.get("detail", ""))


async def _bring_up_to_date(client: httpx.AsyncClient, note_types: list) -> tuple[int, list[str]]:
    """The note types made by an older Notosaurus (their CSS without today's signature):
    their card templates and CSS replaced, the fields and card templates they lack
    added; nothing removed. Returns how many changed, and those whose structure changed
    (a field or a card template added: Anki then asks for a full sync). An AnkiConnect
    too old for these actions: left as they are."""
    changed, restructured = 0, []
    for nt in note_types:
        try:
            if nt.signature in (await _invoke(client, "modelStyling", modelName=nt.name))["css"]:
                continue
            fields = await _invoke(client, "modelFieldNames", modelName=nt.name)
            templates = await _invoke(client, "modelTemplates", modelName=nt.name)
        except AnkiConnectError as e:
            if _unsupported(e):
                return changed, restructured
            raise
        added = False
        for name in (f for f in nt.fields if f not in fields):
            await _invoke(client, "modelFieldAdd", modelName=nt.name, fieldName=name, index=len(fields))
            fields.append(name)
            added = True
        for t in (t for t in nt.templates if t["name"] not in templates):
            card = {"Name": t["name"], "Front": t["qfmt"], "Back": t["afmt"]}
            await _invoke(client, "modelTemplateAdd", modelName=nt.name, template=card)
            added = True
        present = {t["name"]: {"Front": t["qfmt"], "Back": t["afmt"]} for t in nt.templates if t["name"] in templates}
        if present:
            await _invoke(client, "updateModelTemplates", model={"name": nt.name, "templates": present})
        await _invoke(client, "updateModelStyling", model={"name": nt.name, "css": nt.full_css})
        changed += 1
        if added:
            restructured.append(nt.name)
    return changed, restructured


async def _other_notosaurus_notes(client: httpx.AsyncClient, deck: str) -> dict[tuple, list[dict]]:
    """The deck's Notosaurus notes (not its subdecks'), by (family, key field, key value)."""
    name = _search(deck)
    ids = await _invoke(client, "findNotes", query=f'"deck:{name}" -"deck:{name}::*" "note:Notosaurus*"')
    found = {}
    for info in await _invoke(client, "notesInfo", notes=ids) if ids else []:
        kind = family(info.get("modelName", ""))
        for key in ("Front", "Id"):
            if kind and key in info["fields"]:
                found.setdefault((kind, key, info["fields"][key]["value"]), []).append(info)
    return found


async def _sync(client: httpx.AsyncClient, result: SendResult) -> None:
    """Sync with AnkiWeb when the settings ask for it; a failure is told, not fatal."""
    if not settings.current().anki_sync:
        return
    if await sync_configured() is False:
        result.sync_skipped = True  # no AnkiWeb login on this profile: nothing to warn about at each change
        return
    try:
        await _invoke(client, "sync")
        result.synced = True
    except AnkiConnectError as e:  # the change is in Anki anyway
        result.sync_error = e.detail()


def _search(text: str) -> str:
    """A name inside a quoted Anki search: its quotes, backslashes and wildcards escaped."""
    return "".join("\\" + c if c in '\\"*_' else c for c in text)


async def find_lesson_notes(
    lesson_id: str,
    notes: list[Note],
    others: AbstractSet[tuple[str, str]] = frozenset(),
    other_tags: AbstractSet[str] = frozenset(),
) -> list[int]:
    """The lesson's notes in the open profile: those with its tag, and those sent before
    notes had it (same note type and deck, same key). Never a note another lesson uses
    too: tagged for it as well (`other_tags`: the tags of the lessons that still exist),
    or untagged with the deck and key of one of its cards (`others`)."""
    own = TAG_PREFIX + lesson_id
    async with _client() as client:
        tagged = await _invoke(client, "findNotes", query=f'"tag:{_search(own)}"')
        infos = await _invoke(client, "notesInfo", notes=tagged) if tagged else []
        found = {i["noteId"] for i in infos if not other_tags & set(i["tags"])}
        for deck, nt in dict.fromkeys((n.deck, n.nt) for n in notes):
            keys = {n.key for n in notes if (n.deck, n.nt) == (deck, nt)} - {k for d, k in others if d == deck}
            name = _search(deck)
            query = f'"note:{_search(nt.name)}" "deck:{name}" -"deck:{name}::*" -"tag:{_search(TAG_PREFIX)}*"'
            ids = await _invoke(client, "findNotes", query=query)  # this deck (not its subdecks), untagged
            infos = await _invoke(client, "notesInfo", notes=ids) if ids else []
            found.update(i["noteId"] for i in infos if i["fields"].get(nt.key, {}).get("value") in keys)
        return sorted(found)


async def _drop_empty_decks(client: httpx.AsyncClient, decks: set[str]) -> None:
    """`decks` and their parent decks left without any card deleted (a deck still holding
    cards, even in a subdeck, stays; Anki's "Default" too)."""
    parents_too = _with_parents(list(decks)) - {"Default"}
    for deck in sorted(parents_too, key=lambda d: d.count("::"), reverse=True):  # subdecks first
        if not await _invoke(client, "findCards", query=f'"deck:{_search(deck)}"'):
            await _invoke(client, "deleteDecks", decks=[deck], cardsToo=True)


def _with_parents(decks: list[str]) -> set[str]:
    return {"::".join(d.split("::")[: n + 1]) for d in decks for n in range(d.count("::") + 1)}


LEFTOVER_TEXT = 80  # characters of a note's text shown


async def leftovers(lesson_id: str, keep: set[int]) -> list[dict]:
    """The lesson's notes in Anki (its tag) that none of its cards updated (`keep`: the
    notes they did): what is left of cards deleted, or remade with another front (lesson
    generated again). Never a note another lesson uses too. {"id", "text"}, the text
    plain and short, for the parent to see before deleting them."""
    tag = TAG_PREFIX + lesson_id
    async with _client() as client:
        ids = [i for i in await _invoke(client, "findNotes", query=f'"tag:{_search(tag)}"') if i not in keep]
        infos = await _invoke(client, "notesInfo", notes=ids) if ids else []
        infos = [i for i in infos if i and not any(t.startswith(TAG_PREFIX) and t != tag for t in i["tags"])]
        cards = [c for i in infos for c in i.get("cards", [])[:1]]
        decks = {c["note"]: c["deckName"] for c in await _invoke(client, "cardsInfo", cards=cards)} if cards else {}
    return [{"id": i["noteId"], "text": _note_text(i), "deck": decks.get(i["noteId"], "")} for i in infos]


def _note_text(info: dict) -> str:
    """What a note shows first (its front, its text with gaps, its question), plain."""
    fields = info["fields"]
    name = next((f for f in ("Front", "Text", "Question") if f in fields), None)
    name = name or min(fields, key=lambda f: fields[f].get("order", 0), default=None)
    raw = fields[name]["value"] if name else ""
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw)).split())
    return text if len(text) <= LEFTOVER_TEXT else text[: LEFTOVER_TEXT - 1] + "…"


async def delete_notes(ids: list[int], decks: list[str]) -> SendResult:
    """Delete these notes (their review history with them), then `decks` and their parent
    decks left without any card (a deck still holding cards, even in a subdeck, stays;
    Anki's "Default" too), then sync."""
    async with _client() as client:
        if ids:
            await _invoke(client, "deleteNotes", notes=ids)
        await _drop_empty_decks(client, set(decks))
        result = SendResult(added=0, updated=0, synced=False)
        await _sync(client, result)
        return result

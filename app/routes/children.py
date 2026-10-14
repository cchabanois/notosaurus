"""The children's cards (app/children.py): listed, saved by the page's "For: …" sheet."""

import asyncio

from fastapi import APIRouter

from .. import children
from ..errors import AppError

router = APIRouter()


@router.get("/api/children")
async def list_children() -> list[children.Child]:
    return await asyncio.to_thread(children.list_all)


@router.put("/api/children")
async def save_children(cards: list[children.Child]) -> list[children.Child]:
    """The whole list, as the sheet has it (added, changed, removed, in its order)."""
    if len({c.id for c in cards}) != len(cards):
        raise AppError("children.same_id", 400)
    if len(cards) > 20:
        raise AppError("children.too_many", 400, max=20)
    return await asyncio.to_thread(children.save_all, cards)

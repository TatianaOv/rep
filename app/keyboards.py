from __future__ import annotations

from typing import Iterable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.models import Homework


def homework_done_keyboard(items: Iterable[Homework]) -> InlineKeyboardMarkup | None:
    items = [hw for hw in items if not hw.done]
    if not items:
        return None
    rows = []
    for hw in items:
        label = f"✅ {hw.subject}"
        if len(label) > 40:
            label = label[:37] + "..."
        rows.append([InlineKeyboardButton(text=label, callback_data=f"hwdone:{hw.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

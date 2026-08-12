from __future__ import annotations

import secrets

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AiMessage, LinkCode, PlannerSettings, Recipient, Student

AI_HISTORY_CONTEXT_LIMIT = 20  # messages sent to the model as conversation context
AI_HISTORY_RETENTION_LIMIT = 40  # hard cap on stored messages per recipient


async def get_or_create_settings(session: AsyncSession) -> PlannerSettings:
    result = await session.execute(select(PlannerSettings).limit(1))
    row = result.scalar_one_or_none()
    if row is None:
        row = PlannerSettings()
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def get_or_create_student(session: AsyncSession) -> Student:
    result = await session.execute(select(Student).limit(1))
    row = result.scalar_one_or_none()
    if row is None:
        row = Student()
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def get_recipients(session: AsyncSession) -> list[Recipient]:
    result = await session.execute(select(Recipient).order_by(Recipient.linked_at))
    return list(result.scalars().all())


async def find_recipient_by_chat_id(session: AsyncSession, chat_id: int) -> Recipient | None:
    result = await session.execute(select(Recipient).where(Recipient.telegram_chat_id == chat_id))
    return result.scalar_one_or_none()


async def get_pending_link_codes(session: AsyncSession) -> list[LinkCode]:
    result = await session.execute(select(LinkCode).order_by(LinkCode.created_at))
    return list(result.scalars().all())


async def create_link_code(session: AsyncSession, label: str | None) -> LinkCode:
    link_code = LinkCode(code=secrets.token_hex(3), label=label.strip() if label and label.strip() else None)
    session.add(link_code)
    await session.commit()
    await session.refresh(link_code)
    return link_code


async def consume_link_code(session: AsyncSession, code: str) -> LinkCode | None:
    result = await session.execute(select(LinkCode).where(LinkCode.code == code))
    return result.scalar_one_or_none()


async def get_ai_history(session: AsyncSession, recipient_id: int) -> list[AiMessage]:
    result = await session.execute(
        select(AiMessage)
        .where(AiMessage.recipient_id == recipient_id)
        .order_by(AiMessage.created_at.desc())
        .limit(AI_HISTORY_CONTEXT_LIMIT)
    )
    rows = list(result.scalars().all())
    rows.reverse()
    return rows


async def add_ai_message(session: AsyncSession, recipient_id: int, role: str, content: str) -> None:
    session.add(AiMessage(recipient_id=recipient_id, role=role, content=content))
    await session.commit()

    result = await session.execute(
        select(AiMessage.id)
        .where(AiMessage.recipient_id == recipient_id)
        .order_by(AiMessage.created_at.desc())
        .offset(AI_HISTORY_RETENTION_LIMIT)
    )
    old_ids = [row[0] for row in result.all()]
    if old_ids:
        await session.execute(delete(AiMessage).where(AiMessage.id.in_(old_ids)))
        await session.commit()


async def clear_ai_history(session: AsyncSession, recipient_id: int) -> None:
    await session.execute(delete(AiMessage).where(AiMessage.recipient_id == recipient_id))
    await session.commit()

from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LinkCode, PlannerSettings, Recipient, Student


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

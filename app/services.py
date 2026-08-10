from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PlannerSettings, Student


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

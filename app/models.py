from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Time, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), default="Дочь")
    telegram_chat_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    telegram_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    linked_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    day_of_week: Mapped[int] = mapped_column(Integer)  # 0 = Monday ... 6 = Sunday
    start_time: Mapped[dt.time] = mapped_column(Time)
    end_time: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    subject: Mapped[str] = mapped_column(String(200))
    room: Mapped[str | None] = mapped_column(String(50), nullable=True)
    teacher: Mapped[str | None] = mapped_column(String(100), nullable=True)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Homework(Base):
    __tablename__ = "homework"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000))
    due_date: Mapped[dt.date] = mapped_column(Date)
    due_time: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class PlannerSettings(Base):
    __tablename__ = "planner_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    morning_digest_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    morning_digest_time: Mapped[dt.time] = mapped_column(Time, default=dt.time(7, 30))
    lesson_reminder_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True, default=15)
    homework_reminder_time: Mapped[dt.time] = mapped_column(Time, default=dt.time(19, 0))
    homework_reminder_days_before: Mapped[int] = mapped_column(Integer, default=1)
    link_code: Mapped[str | None] = mapped_column(String(20), nullable=True)


class ReminderLog(Base):
    __tablename__ = "reminder_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sent_date: Mapped[dt.date] = mapped_column(Date)
    sent_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("kind", "ref_id", "sent_date", name="uq_reminder_dedupe"),)

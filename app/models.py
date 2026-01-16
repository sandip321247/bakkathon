from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


def utcnow():
    """timezone-aware UTC now"""
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=utcnow)


class Goal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    title: str
    description: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    due_date: Optional[datetime] = None
    completed: bool = False


class Timeline(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    name: str = "prime"
    parent_timeline_id: Optional[int] = Field(default=None, index=True)
    stability: float = 1.0
    created_at: datetime = Field(default_factory=utcnow)


class TimeSelfMemory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    timeline_id: int = Field(index=True)
    time_self: str  # PAST, PRESENT, FUTURE
    memory_json: str = "{}"
    last_updated: datetime = Field(default_factory=utcnow)
    corruption: float = 0.0


class TemporalContract(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    timeline_id: int = Field(index=True)
    contract_text: str
    created_at: datetime = Field(default_factory=utcnow)

    prev_hash: str = ""
    contract_hash: str = ""


class TimePrison(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    locked: bool = False
    reason: str = ""
    unlock_condition: str = ""
    updated_at: datetime = Field(default_factory=utcnow)

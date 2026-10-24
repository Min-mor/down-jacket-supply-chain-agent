"""数据库：SQLAlchemy 2.0。

默认 SQLite（data/agent.db，零配置）；生产可把 DATABASE_URL 切到 Postgres。
表：conversation（会话）、message（消息）。
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversation"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(120), default="新会话")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Message(Base):
    __tablename__ = "message"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversation.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))           # user / assistant
    content: Mapped[str] = mapped_column(Text)
    agent_name: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# 确保 SQLite 目录存在
if settings.database_url.startswith("sqlite"):
    _db_path = settings.database_url.split("///")[-1]
    _dir = os.path.dirname(_db_path)
    if _dir:
        os.makedirs(_dir, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """建表（幂等）。生产用迁移工具管理 schema，这里仅做初始化兜底。"""
    Base.metadata.create_all(bind=engine)


def get_session():
    """FastAPI 依赖：请求级数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

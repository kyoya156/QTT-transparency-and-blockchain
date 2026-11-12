"""Schema chatbot cong khai. Chunk la ban sao chi-doc cua noi dung crawler (web + bai Page)."""
import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, literal_column
from sqlalchemy.orm import Mapped, column_property, mapped_column

from .config import settings
from .db import Base


EMBED_DIM = settings.embed_dim


def _now():
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    src_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)   # id cua chunk ben crawler
    source_type: Mapped[str] = mapped_column(String(16), index=True)        # web | post
    source_id: Mapped[str] = mapped_column(String(128), index=True)
    content: Mapped[str] = mapped_column(Text())
    content_hash: Mapped[str] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    title: Mapped[str | None] = mapped_column(Text(), nullable=True)
    part: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_date: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    crawled_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime.datetime] = _now()
    # NULL = chua embed (hoac noi dung vua doi). M2 se dien.
    embedding: Mapped[list | None] = mapped_column(Vector(settings.embed_dim), nullable=True)
    embed_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Khop dung bieu thuc cua index GIN ix_chunks_fts (xem migrations.py); khong phai cot that.
    tsv = column_property(
        func.to_tsvector(literal_column("'simple'::regconfig"), func.immutable_unaccent(content)),
        deferred=True,
    )

    @property
    def display_date(self):
        return self.source_date or self.crawled_at


class SyncRun(Base):
    __tablename__ = "sync_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime.datetime] = _now()
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    inserted: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    deleted: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text(), nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime.datetime] = _now()


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))                 # user | assistant
    text: Mapped[str] = mapped_column(Text())
    intent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    evidence_ids: Mapped[str | None] = mapped_column(Text(), nullable=True)   # JSON list chunk id
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = _now()


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), index=True)
    value: Mapped[str] = mapped_column(String(8))                 # up | down
    note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime.datetime] = _now()


class Handoff(Base):
    __tablename__ = "handoffs"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    reason: Mapped[str] = mapped_column(String(64))
    transcript: Mapped[str] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime.datetime] = _now()

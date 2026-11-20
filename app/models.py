"""Schema chatbot cong khai. Chunk la ban sao chi-doc cua noi dung crawler (web + bai Page)."""
import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func, literal_column
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
    # Phong ban duoc doc chunk nay (admin luon duoc). Rong = chua gan nhan = chi admin. RLS dung cot nay.
    labels: Mapped[list] = mapped_column(ARRAY(String(32)).with_variant(JSON(), "sqlite"), default=list)
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
        """The date shown under an answer: the page's own date, else the crawl date."""
        value = self.source_date or self.crawled_at
        return value.date() if isinstance(value, datetime.datetime) else value


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
    claimed_by: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    claimed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime.datetime] = _now()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    department: Mapped[str] = mapped_column(String(32))          # admin | dev | finance | volunteer
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = _now()


class AccessRule(Base):
    """Nhan do admin gan: key = 'source:<type>:<id|*>' hoac 'tool:<ten>'; departments = phong ban (khong gom admin)."""
    __tablename__ = "access_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(400), unique=True, index=True)
    departments: Mapped[list] = mapped_column(JSON, default=list)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime.datetime] = _now()


class AuditLog(Base):
    """Chi them, khong sua/xoa (vai tro chatbot_app chi co INSERT)."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime.datetime] = _now()
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    department: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(32), index=True)  # search | tool_denied | label_change | user_change
    query: Mapped[str | None] = mapped_column(Text(), nullable=True)
    chunk_ids: Mapped[str | None] = mapped_column(Text(), nullable=True)   # JSON list
    detail: Mapped[str | None] = mapped_column(Text(), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)   # vd "ticket:12"


class CorrectionTicket(Base):
    """Phieu de nghi sua so lieu. finance/volunteer de nghi -> admin duyet -> dev ap dung (tach nhiem vu)."""
    __tablename__ = "correction_tickets"
    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    table_name: Mapped[str] = mapped_column(String(64))
    record_id: Mapped[str] = mapped_column(String(128))
    field_name: Mapped[str] = mapped_column(String(64))
    current_value: Mapped[str | None] = mapped_column(Text(), nullable=True)
    proposed_value: Mapped[str] = mapped_column(Text())
    reason: Mapped[str] = mapped_column(Text())
    evidence: Mapped[str | None] = mapped_column(Text(), nullable=True)      # tham chieu: ma giao dich, tin nhan...
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)  # open|approved|rejected|applied|cancelled
    created_at: Mapped[datetime.datetime] = _now()
    decided_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decided_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text(), nullable=True)
    applied_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    applied_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_value: Mapped[str | None] = mapped_column(Text(), nullable=True)
    apply_note: Mapped[str | None] = mapped_column(Text(), nullable=True)

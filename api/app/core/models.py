import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    Computed,
    Date,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func
from sqlalchemy.sql.sqltypes import DateTime


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(255), nullable=False)
    url = Column(Text)
    category = Column(String(100))
    subcategory = Column(String(100))
    title = Column(Text)
    raw_content = Column(Text, nullable=False)
    clean_content = Column(Text)
    word_count = Column(Integer)
    language = Column(String(10), server_default="fr")
    published_at = Column(Date)
    collected_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime)
    embedding = Column(Vector(384))
    doc_metadata = Column("metadata", JSONB)
    status = Column(String(20), server_default="active")
    fts_vector = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('french', coalesce(clean_content, '') || ' ' || coalesce(title, ''))",
            persisted=True,
        ),
    )

    __table_args__ = (
        Index("documents_source_idx", "source"),
        Index("documents_category_idx", "category"),
        Index("documents_language_idx", "language"),
        Index("documents_status_collected_at_idx", "status", "collected_at"),
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    word_count = Column(Integer)
    embedding = Column(Vector(384))

    __table_args__ = (Index("chunks_document_id_idx", "document_id"),)


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash = Column(String(64), nullable=False, unique=True)
    key_prefix = Column(String(20))
    owner_name = Column(String(255))
    owner_email = Column(String(255))
    use_case = Column(Text)
    plan = Column(String(20), server_default="free")
    is_active = Column(Boolean, server_default="true")
    created_at = Column(DateTime, server_default=func.now())
    last_used = Column(DateTime)

    __table_args__ = (
        Index("api_keys_hash_idx", "key_hash"),
        Index("api_keys_active_idx", "is_active"),
    )


class UserQuery(Base):
    __tablename__ = "user_queries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question = Column(Text, nullable=False)
    language = Column(String(10), server_default="fr")
    category = Column(String(100))
    is_off_topic = Column(Boolean, server_default="false")
    chunks_found = Column(Integer, server_default="0")
    latency_ms = Column(Integer)
    api_key_prefix = Column(String(20))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("user_queries_created_at_idx", "created_at"),
        Index("user_queries_api_key_prefix_idx", "api_key_prefix"),
    )

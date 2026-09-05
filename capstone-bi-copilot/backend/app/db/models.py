from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base

def utcnow(): return datetime.now(timezone.utc)

class User(Base):
    __tablename__="users"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    email: Mapped[str]=mapped_column(String(255),unique=True,index=True)
    password_hash: Mapped[str]=mapped_column(String(512))
    role: Mapped[str]=mapped_column(String(32),default="manager",index=True)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class Conversation(Base):
    __tablename__="conversations"
    id: Mapped[str]=mapped_column(String(80),primary_key=True)
    user_id: Mapped[int | None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    title: Mapped[str]=mapped_column(String(255),default="New conversation")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class Message(Base):
    __tablename__="messages"
    id: Mapped[str]=mapped_column(String(80),primary_key=True)
    conversation_id: Mapped[str]=mapped_column(ForeignKey("conversations.id"),index=True)
    role: Mapped[str]=mapped_column(String(16))
    content: Mapped[str]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class ToolAction(Base):
    __tablename__="tool_actions"
    id: Mapped[str]=mapped_column(String(80),primary_key=True)
    message_id: Mapped[str]=mapped_column(ForeignKey("messages.id"),unique=True,index=True)
    user_id: Mapped[int | None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    tool_name: Mapped[str]=mapped_column(String(120),index=True)
    arguments_json: Mapped[str]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(24),default="proposed",index=True)
    result_json: Mapped[str | None]=mapped_column(Text,nullable=True)
    error: Mapped[str | None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow,onupdate=utcnow)

class Sale(Base):
    __tablename__="sales"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    sale_date: Mapped[str]=mapped_column(String(10),index=True)
    region: Mapped[str]=mapped_column(String(80),index=True)
    product: Mapped[str]=mapped_column(String(120),index=True)
    revenue: Mapped[float]=mapped_column(Float)
    cost: Mapped[float]=mapped_column(Float)
    orders: Mapped[int]=mapped_column(Integer)

class Document(Base):
    __tablename__="documents"
    id: Mapped[str]=mapped_column(String(80),primary_key=True)
    filename: Mapped[str]=mapped_column(String(255))
    mime_type: Mapped[str]=mapped_column(String(120),default="application/octet-stream")
    allowed_roles: Mapped[str]=mapped_column(String(255),default="admin,executive,manager,analyst,employee")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class DocumentChunk(Base):
    __tablename__="document_chunks"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    document_id: Mapped[str]=mapped_column(ForeignKey("documents.id"),index=True)
    chunk_index: Mapped[int]=mapped_column(Integer)
    text: Mapped[str]=mapped_column(Text)

class ReportRecord(Base):
    __tablename__="reports"
    id: Mapped[str]=mapped_column(String(80),primary_key=True)
    title: Mapped[str]=mapped_column(String(255))
    format: Mapped[str]=mapped_column(String(16))
    path: Mapped[str]=mapped_column(String(1024))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class AuditLog(Base):
    __tablename__="audit_logs"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id: Mapped[int | None]=mapped_column(Integer,nullable=True,index=True)
    action: Mapped[str]=mapped_column(String(120),index=True)
    detail: Mapped[str]=mapped_column(Text,default="")
    request_id: Mapped[str]=mapped_column(String(80),index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)

class DocumentFolder(Base):
    __tablename__ = "document_folders"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    parent_folder_id: Mapped[str | None] = mapped_column(ForeignKey("document_folders.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class DocumentDetails(Base):
    """Additive metadata keeps existing document tables and ingestion contracts intact."""
    __tablename__ = "document_details"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    folder_id: Mapped[str | None] = mapped_column(ForeignKey("document_folders.id"), nullable=True, index=True)
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class OAuthConnection(Base):
    __tablename__ = "oauth_connections"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_oauth_connection_user_provider"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    account_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class OAuthState(Base):
    __tablename__ = "oauth_states"
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

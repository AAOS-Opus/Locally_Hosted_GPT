"""
SQLAlchemy models for Sovereign Assistant API.

Defines the schema for assistants, conversation threads, and messages.
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    JSON,
    create_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class MessageRole(PyEnum):
    """Enum for message roles."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Assistant(Base):
    """Model for assistant configurations."""

    __tablename__ = "assistants"

    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    instructions = Column(Text, nullable=False)
    model = Column(String(100), nullable=False, default="gpt-4")
    created_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    threads = relationship(
        "Thread",
        back_populates="assistant",
        cascade="all, delete-orphan",
        foreign_keys="Thread.assistant_id",
    )

    def __repr__(self) -> str:
        return (
            f"<Assistant(id='{self.id}', name='{self.name}', "
            f"model='{self.model}', created_at={self.created_at})>"
        )

    def validate(self) -> None:
        """Validate assistant configuration."""
        if not self.instructions or not self.instructions.strip():
            raise ValueError("Instructions cannot be empty")


class Thread(Base):
    """Model for conversation threads."""

    __tablename__ = "threads"

    id = Column(String(36), primary_key=True, index=True)
    assistant_id = Column(
        String(36), ForeignKey("assistants.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    thread_metadata = Column(JSON, nullable=True, default={})

    # Relationships
    assistant = relationship("Assistant", back_populates="threads")
    messages = relationship(
        "Message",
        back_populates="thread",
        cascade="all, delete-orphan",
        foreign_keys="Message.thread_id",
    )

    # Indexes for frequently queried columns
    __table_args__ = (Index("idx_thread_assistant_id", "assistant_id"),)

    def __repr__(self) -> str:
        return (
            f"<Thread(id='{self.id}', assistant_id='{self.assistant_id}', "
            f"created_at={self.created_at}, message_count={len(self.messages)})>"
        )


class Message(Base):
    """Model for individual messages in a conversation."""

    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, index=True)
    thread_id = Column(
        String(36), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(
        Enum(MessageRole), nullable=False, default=MessageRole.USER, index=True
    )
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    token_count = Column(Integer, nullable=True, default=0)

    # Relationships
    thread = relationship("Thread", back_populates="messages", uselist=False)

    # Indexes for frequently queried columns
    __table_args__ = (Index("idx_message_thread_id", "thread_id"),)

    def __repr__(self) -> str:
        return (
            f"<Message(id='{self.id}', thread_id='{self.thread_id}', "
            f"role='{self.role.value}', timestamp={self.timestamp})>"
        )

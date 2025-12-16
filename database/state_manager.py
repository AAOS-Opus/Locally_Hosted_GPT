"""
StateManager for handling database operations in Sovereign Assistant API.

Provides CRUD operations for assistants, threads, and messages with proper
session management, error handling, and transaction safety.
"""

import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, desc
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Assistant, Thread, Message, MessageRole

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class StateManagerException(Exception):
    """Base exception for StateManager operations."""

    pass


class AssistantNotFound(StateManagerException):
    """Exception raised when an assistant is not found."""

    pass


class ThreadNotFound(StateManagerException):
    """Exception raised when a thread is not found."""

    pass


class MessageNotFound(StateManagerException):
    """Exception raised when a message is not found."""

    pass


class StateManager:
    """
    Manages all database operations for Sovereign Assistant API.

    Provides session management with context managers, comprehensive error
    handling, and transaction safety with automatic rollback on errors.
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        echo: bool = False,
    ) -> None:
        """
        Initialize StateManager with database connection.

        Args:
            database_url: Database URL for SQLAlchemy engine.
                         If not provided, reads from DATABASE_URL environment variable.
                         Defaults to sqlite:///data/sovereign_assistant.db if neither is set.
            echo: Enable SQL query logging. Defaults to False.
        """
        # Read from environment variable if not explicitly provided
        if database_url is None:
            database_url = os.getenv("DATABASE_URL", "sqlite:///data/sovereign_assistant.db")
        
        self.database_url = database_url
        self.engine = create_engine(database_url, echo=echo)
        # Use expire_on_commit=False to prevent detached instance errors
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._ensure_tables()
        logger.info(f"StateManager initialized with database: {database_url}")

    def _ensure_tables(self) -> None:
        """Create all tables if they don't exist."""
        Base.metadata.create_all(self.engine)
        logger.info("Database tables ensured")

    @contextmanager
    def get_session(self) -> Session:
        """
        Context manager for database sessions.

        Yields a session with automatic commit on success and rollback on error.

        Yields:
            SQLAlchemy Session instance

        Raises:
            SQLAlchemyError: If session operations fail
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
            logger.debug("Session committed successfully")
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error, rolling back: {str(e)}")
            raise StateManagerException(f"Database operation failed: {str(e)}") from e
        except Exception as e:
            session.rollback()
            logger.error(f"Unexpected error, rolling back: {str(e)}")
            raise
        finally:
            session.close()

    # ASSISTANT OPERATIONS

    def create_assistant(
        self,
        name: str,
        instructions: str,
        model: str = "gpt-4",
        assistant_id: Optional[str] = None,
    ) -> Assistant:
        """
        Create a new assistant.

        Args:
            name: Assistant name
            instructions: System instructions for the assistant
            model: LLM model identifier (default: gpt-4)
            assistant_id: Optional custom ID. If not provided, generates UUID.

        Returns:
            Created Assistant instance

        Raises:
            StateManagerException: If assistant creation fails
        """
        try:
            if not instructions or not instructions.strip():
                raise ValueError("Instructions cannot be empty")

            assistant_id = assistant_id or str(uuid.uuid4())

            with self.get_session() as session:
                assistant = Assistant(
                    id=assistant_id,
                    name=name,
                    instructions=instructions,
                    model=model,
                )
                session.add(assistant)
                logger.info(f"Created assistant: {assistant_id}")

            return assistant
        except ValueError as e:
            raise StateManagerException(str(e)) from e

    def get_assistant(self, assistant_id: str) -> Assistant:
        """
        Get an assistant by ID.

        Args:
            assistant_id: Assistant ID to retrieve

        Returns:
            Assistant instance

        Raises:
            AssistantNotFound: If assistant does not exist
        """
        with self.get_session() as session:
            assistant = session.query(Assistant).filter_by(id=assistant_id).first()

        if not assistant:
            raise AssistantNotFound(f"Assistant not found: {assistant_id}")

        logger.debug(f"Retrieved assistant: {assistant_id}")
        return assistant

    def update_assistant(
        self,
        assistant_id: str,
        name: Optional[str] = None,
        instructions: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Assistant:
        """
        Update an existing assistant.

        Args:
            assistant_id: Assistant ID to update
            name: New name (optional)
            instructions: New instructions (optional)
            model: New model identifier (optional)

        Returns:
            Updated Assistant instance

        Raises:
            AssistantNotFound: If assistant does not exist
            StateManagerException: If update fails
        """
        try:
            with self.get_session() as session:
                assistant = session.query(Assistant).filter_by(id=assistant_id).first()

                if not assistant:
                    raise AssistantNotFound(f"Assistant not found: {assistant_id}")

                if name is not None:
                    assistant.name = name
                if instructions is not None:
                    if not instructions.strip():
                        raise ValueError("Instructions cannot be empty")
                    assistant.instructions = instructions
                if model is not None:
                    assistant.model = model

                assistant.updated_at = datetime.utcnow()
                logger.info(f"Updated assistant: {assistant_id}")

            return assistant
        except AssistantNotFound:
            raise
        except ValueError as e:
            raise StateManagerException(str(e)) from e

    def delete_assistant(self, assistant_id: str) -> bool:
        """
        Delete an assistant (cascades to threads and messages).

        Args:
            assistant_id: Assistant ID to delete

        Returns:
            True if assistant was deleted

        Raises:
            AssistantNotFound: If assistant does not exist
        """
        with self.get_session() as session:
            assistant = session.query(Assistant).filter_by(id=assistant_id).first()

            if not assistant:
                raise AssistantNotFound(f"Assistant not found: {assistant_id}")

            session.delete(assistant)
            logger.info(f"Deleted assistant and associated data: {assistant_id}")

        return True

    def list_assistants(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Assistant]:
        """
        List all assistants with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of Assistant instances
        """
        with self.get_session() as session:
            assistants = (
                session.query(Assistant)
                .order_by(desc(Assistant.created_at))
                .offset(skip)
                .limit(limit)
                .all()
            )
            logger.debug(f"Listed {len(assistants)} assistants")

        return assistants

    # THREAD OPERATIONS

    def create_thread(
        self,
        assistant_id: str,
        thread_id: Optional[str] = None,
        thread_metadata: Optional[Dict[str, Any]] = None,
    ) -> Thread:
        """
        Create a new conversation thread.

        Args:
            assistant_id: ID of the associated assistant
            thread_id: Optional custom ID. If not provided, generates UUID.
            thread_metadata: Optional JSON metadata for extensibility

        Returns:
            Created Thread instance

        Raises:
            AssistantNotFound: If assistant does not exist
            StateManagerException: If thread creation fails
        """
        try:
            # Verify assistant exists
            self.get_assistant(assistant_id)

            thread_id = thread_id or str(uuid.uuid4())

            with self.get_session() as session:
                thread = Thread(
                    id=thread_id,
                    assistant_id=assistant_id,
                    thread_metadata=thread_metadata or {},
                )
                session.add(thread)
                logger.info(f"Created thread: {thread_id} for assistant: {assistant_id}")

            return thread
        except AssistantNotFound:
            raise

    def get_thread(self, thread_id: str) -> Thread:
        """
        Get a thread by ID.

        Args:
            thread_id: Thread ID to retrieve

        Returns:
            Thread instance with relationships loaded

        Raises:
            ThreadNotFound: If thread does not exist
        """
        with self.get_session() as session:
            thread = (
                session.query(Thread)
                .filter_by(id=thread_id)
                .first()
            )

        if not thread:
            raise ThreadNotFound(f"Thread not found: {thread_id}")

        logger.debug(f"Retrieved thread: {thread_id}")
        return thread

    def update_thread(
        self,
        thread_id: str,
        thread_metadata: Optional[Dict[str, Any]] = None,
    ) -> Thread:
        """
        Update an existing thread.

        Args:
            thread_id: Thread ID to update
            thread_metadata: New metadata (optional)

        Returns:
            Updated Thread instance

        Raises:
            ThreadNotFound: If thread does not exist
        """
        with self.get_session() as session:
            thread = session.query(Thread).filter_by(id=thread_id).first()

            if not thread:
                raise ThreadNotFound(f"Thread not found: {thread_id}")

            if thread_metadata is not None:
                thread.thread_metadata = thread_metadata

            thread.updated_at = datetime.utcnow()
            logger.info(f"Updated thread: {thread_id}")

        return thread

    def delete_thread(self, thread_id: str) -> bool:
        """
        Delete a thread (cascades to messages).

        Args:
            thread_id: Thread ID to delete

        Returns:
            True if thread was deleted

        Raises:
            ThreadNotFound: If thread does not exist
        """
        with self.get_session() as session:
            thread = session.query(Thread).filter_by(id=thread_id).first()

            if not thread:
                raise ThreadNotFound(f"Thread not found: {thread_id}")

            session.delete(thread)
            logger.info(f"Deleted thread and associated messages: {thread_id}")

        return True

    def list_threads(
        self,
        assistant_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Thread]:
        """
        List threads with optional filtering by assistant.

        Args:
            assistant_id: Optional assistant ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of Thread instances
        """
        with self.get_session() as session:
            query = session.query(Thread)

            if assistant_id:
                query = query.filter_by(assistant_id=assistant_id)

            threads = (
                query.order_by(desc(Thread.created_at))
                .offset(skip)
                .limit(limit)
                .all()
            )
            logger.debug(f"Listed {len(threads)} threads")

        return threads

    # MESSAGE OPERATIONS

    def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        token_count: Optional[int] = None,
    ) -> Message:
        """
        Add a message to a thread.

        Args:
            thread_id: Thread ID to add message to
            role: Message role (system, user, or assistant)
            content: Message content
            token_count: Optional token count for context management

        Returns:
            Created Message instance

        Raises:
            ThreadNotFound: If thread does not exist
            StateManagerException: If message creation fails
        """
        try:
            # Verify thread exists
            self.get_thread(thread_id)

            # Validate role
            try:
                message_role = MessageRole[role.upper()]
            except KeyError:
                raise ValueError(
                    f"Invalid role: {role}. Must be one of: "
                    f"{', '.join([r.value for r in MessageRole])}"
                )

            message_id = str(uuid.uuid4())

            with self.get_session() as session:
                message = Message(
                    id=message_id,
                    thread_id=thread_id,
                    role=message_role,
                    content=content,
                    token_count=token_count or 0,
                )
                session.add(message)
                logger.info(f"Added message: {message_id} to thread: {thread_id}")

            return message
        except ThreadNotFound:
            raise
        except ValueError as e:
            raise StateManagerException(str(e)) from e

    def get_messages(
        self,
        thread_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Message]:
        """
        Get messages from a thread in chronological order.

        Args:
            thread_id: Thread ID to retrieve messages from
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of Message instances ordered by timestamp

        Raises:
            ThreadNotFound: If thread does not exist
        """
        # Verify thread exists
        self.get_thread(thread_id)

        with self.get_session() as session:
            messages = (
                session.query(Message)
                .filter_by(thread_id=thread_id)
                .order_by(Message.timestamp)
                .offset(skip)
                .limit(limit)
                .all()
            )
            logger.debug(f"Retrieved {len(messages)} messages from thread: {thread_id}")

        return messages

    def get_thread_context(self, thread_id: str) -> Dict[str, Any]:
        """
        Get complete thread context for inference.

        Loads thread with all messages in chronological order, ready for
        passing to LLM for inference.

        Args:
            thread_id: Thread ID to load context for

        Returns:
            Dictionary containing thread and messages ready for inference

        Raises:
            ThreadNotFound: If thread does not exist
        """
        with self.get_session() as session:
            thread = (
                session.query(Thread)
                .filter_by(id=thread_id)
                .first()
            )

            if not thread:
                raise ThreadNotFound(f"Thread not found: {thread_id}")

            messages = (
                session.query(Message)
                .filter_by(thread_id=thread_id)
                .order_by(Message.timestamp)
                .all()
            )

            logger.debug(f"Loaded context for thread: {thread_id} with {len(messages)} messages")

            return {
                "thread_id": thread.id,
                "assistant_id": thread.assistant_id,
                "created_at": thread.created_at.isoformat(),
                "updated_at": thread.updated_at.isoformat(),
                "messages": [
                    {
                        "id": msg.id,
                        "role": msg.role.value,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "token_count": msg.token_count,
                    }
                    for msg in messages
                ],
            }

    def delete_old_messages(
        self,
        thread_id: str,
        keep_count: int = 10,
    ) -> int:
        """
        Delete old messages from a thread, keeping only the most recent ones.

        Useful for managing context window size in long conversations.

        Args:
            thread_id: Thread ID to prune messages from
            keep_count: Number of most recent messages to keep

        Returns:
            Number of messages deleted

        Raises:
            ThreadNotFound: If thread does not exist
        """
        # Verify thread exists
        self.get_thread(thread_id)

        with self.get_session() as session:
            # Get all messages ordered by timestamp
            messages = (
                session.query(Message)
                .filter_by(thread_id=thread_id)
                .order_by(Message.timestamp)
                .all()
            )

            # Calculate how many to delete
            delete_count = max(0, len(messages) - keep_count)

            if delete_count > 0:
                # Delete oldest messages
                messages_to_delete = messages[:delete_count]
                for msg in messages_to_delete:
                    session.delete(msg)

                logger.info(
                    f"Deleted {delete_count} old messages from thread: {thread_id}, "
                    f"keeping {keep_count} most recent"
                )

        return delete_count

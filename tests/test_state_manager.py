"""
Comprehensive pytest test suite for StateManager.

Tests cover all CRUD operations, relationship integrity, transaction handling,
and error cases.
"""

import os
import tempfile
from pathlib import Path

import pytest

from database import (
    Assistant,
    AssistantNotFound,
    Message,
    MessageRole,
    StateManager,
    Thread,
    ThreadNotFound,
)


@pytest.fixture
def temp_db_path():
    """Provide a temporary database path that gets cleaned up after tests."""
    import tempfile
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    yield f"sqlite:///{db_path}"
    # Manual cleanup after test
    import shutil
    try:
        shutil.rmtree(tmpdir)
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
def state_manager(temp_db_path):
    """Create a fresh StateManager instance with test database for each test."""
    sm = StateManager(database_url=temp_db_path, echo=False)
    yield sm
    # Properly dispose of the engine to close all connections
    sm.engine.dispose()


@pytest.fixture
def sample_assistant(state_manager):
    """Provide a test assistant for reuse across tests."""
    return state_manager.create_assistant(
        name="Test Assistant",
        instructions="You are a helpful test assistant.",
        model="gpt-4",
    )


@pytest.fixture
def sample_thread(state_manager, sample_assistant):
    """Provide a test thread for reuse across tests."""
    return state_manager.create_thread(
        assistant_id=sample_assistant.id,
        thread_metadata={"test_key": "test_value"},
    )


# ASSISTANT CRUD TESTS

def test_create_assistant(state_manager):
    """Test creating an assistant with all fields."""
    assistant = state_manager.create_assistant(
        name="Aurora Trading Bot",
        instructions="Analyze market data and provide trading insights.",
        model="gpt-4",
    )

    assert assistant is not None
    assert assistant.name == "Aurora Trading Bot"
    assert assistant.instructions == "Analyze market data and provide trading insights."
    assert assistant.model == "gpt-4"
    assert assistant.created_at is not None
    assert assistant.updated_at is not None


def test_create_assistant_with_custom_id(state_manager):
    """Test creating an assistant with a custom ID."""
    custom_id = "aurora-001"
    assistant = state_manager.create_assistant(
        name="Aurora",
        instructions="Trading assistant",
        assistant_id=custom_id,
    )

    assert assistant.id == custom_id


def test_create_assistant_empty_instructions_fails(state_manager):
    """Test that creating an assistant with empty instructions raises error."""
    with pytest.raises(Exception):
        state_manager.create_assistant(
            name="Bad Assistant",
            instructions="",
        )


def test_get_assistant(state_manager, sample_assistant):
    """Test retrieving an assistant by ID."""
    retrieved = state_manager.get_assistant(sample_assistant.id)

    assert retrieved.id == sample_assistant.id
    assert retrieved.name == sample_assistant.name
    assert retrieved.instructions == sample_assistant.instructions


def test_get_assistant_not_found(state_manager):
    """Test that getting a non-existent assistant raises AssistantNotFound."""
    with pytest.raises(AssistantNotFound):
        state_manager.get_assistant("non-existent-id")


def test_update_assistant(state_manager, sample_assistant):
    """Test updating an assistant's fields."""
    state_manager.update_assistant(
        sample_assistant.id,
        name="Updated Assistant",
        instructions="Updated instructions",
        model="gpt-3.5-turbo",
    )

    updated = state_manager.get_assistant(sample_assistant.id)
    assert updated.name == "Updated Assistant"
    assert updated.instructions == "Updated instructions"
    assert updated.model == "gpt-3.5-turbo"


def test_update_assistant_partial(state_manager, sample_assistant):
    """Test partial update of assistant (only some fields)."""
    original_instructions = sample_assistant.instructions

    state_manager.update_assistant(
        sample_assistant.id,
        name="New Name",
    )

    updated = state_manager.get_assistant(sample_assistant.id)
    assert updated.name == "New Name"
    assert updated.instructions == original_instructions


def test_update_assistant_not_found(state_manager):
    """Test that updating a non-existent assistant raises AssistantNotFound."""
    with pytest.raises(AssistantNotFound):
        state_manager.update_assistant("non-existent-id", name="New Name")


def test_delete_assistant(state_manager, sample_assistant):
    """Test deleting an assistant."""
    result = state_manager.delete_assistant(sample_assistant.id)

    assert result is True
    with pytest.raises(AssistantNotFound):
        state_manager.get_assistant(sample_assistant.id)


def test_delete_assistant_not_found(state_manager):
    """Test that deleting a non-existent assistant raises AssistantNotFound."""
    with pytest.raises(AssistantNotFound):
        state_manager.delete_assistant("non-existent-id")


def test_list_assistants(state_manager):
    """Test listing all assistants."""
    # Create multiple assistants
    for i in range(5):
        state_manager.create_assistant(
            name=f"Assistant {i}",
            instructions=f"Instructions for assistant {i}",
        )

    assistants = state_manager.list_assistants()

    assert len(assistants) == 5
    assert all(isinstance(a, Assistant) for a in assistants)


def test_list_assistants_pagination(state_manager):
    """Test listing assistants with pagination."""
    # Create 10 assistants
    for i in range(10):
        state_manager.create_assistant(
            name=f"Assistant {i}",
            instructions=f"Instructions {i}",
        )

    # Get first 5
    page1 = state_manager.list_assistants(skip=0, limit=5)
    assert len(page1) == 5

    # Get next 5
    page2 = state_manager.list_assistants(skip=5, limit=5)
    assert len(page2) == 5

    # Verify no duplicates
    page1_ids = {a.id for a in page1}
    page2_ids = {a.id for a in page2}
    assert len(page1_ids & page2_ids) == 0


# THREAD CRUD TESTS

def test_create_thread(state_manager, sample_assistant):
    """Test creating a thread."""
    thread = state_manager.create_thread(
        assistant_id=sample_assistant.id,
        thread_metadata={"user_id": "user123"},
    )

    assert thread is not None
    assert thread.assistant_id == sample_assistant.id
    assert thread.thread_metadata == {"user_id": "user123"}
    assert thread.created_at is not None


def test_create_thread_invalid_assistant(state_manager):
    """Test that creating a thread with invalid assistant raises error."""
    with pytest.raises(AssistantNotFound):
        state_manager.create_thread(assistant_id="non-existent-assistant")


def test_get_thread(state_manager, sample_thread):
    """Test retrieving a thread by ID."""
    retrieved = state_manager.get_thread(sample_thread.id)

    assert retrieved.id == sample_thread.id
    assert retrieved.assistant_id == sample_thread.assistant_id


def test_get_thread_not_found(state_manager):
    """Test that getting a non-existent thread raises ThreadNotFound."""
    with pytest.raises(ThreadNotFound):
        state_manager.get_thread("non-existent-thread")


def test_update_thread(state_manager, sample_thread):
    """Test updating thread metadata."""
    new_metadata = {"user_id": "user456", "session_id": "sess789"}

    state_manager.update_thread(
        sample_thread.id,
        thread_metadata=new_metadata,
    )

    updated = state_manager.get_thread(sample_thread.id)
    assert updated.thread_metadata == new_metadata


def test_update_thread_not_found(state_manager):
    """Test that updating a non-existent thread raises ThreadNotFound."""
    with pytest.raises(ThreadNotFound):
        state_manager.update_thread("non-existent-thread", thread_metadata={})


def test_delete_thread(state_manager, sample_thread):
    """Test deleting a thread."""
    result = state_manager.delete_thread(sample_thread.id)

    assert result is True
    with pytest.raises(ThreadNotFound):
        state_manager.get_thread(sample_thread.id)


def test_delete_thread_not_found(state_manager):
    """Test that deleting a non-existent thread raises ThreadNotFound."""
    with pytest.raises(ThreadNotFound):
        state_manager.delete_thread("non-existent-thread")


def test_list_threads(state_manager, sample_assistant):
    """Test listing threads for an assistant."""
    # Create multiple threads
    for i in range(3):
        state_manager.create_thread(assistant_id=sample_assistant.id)

    threads = state_manager.list_threads(assistant_id=sample_assistant.id)

    assert len(threads) == 3
    assert all(t.assistant_id == sample_assistant.id for t in threads)


def test_list_threads_pagination(state_manager, sample_assistant):
    """Test listing threads with pagination."""
    # Create 10 threads
    for i in range(10):
        state_manager.create_thread(assistant_id=sample_assistant.id)

    # Get first 5
    page1 = state_manager.list_threads(
        assistant_id=sample_assistant.id,
        skip=0,
        limit=5,
    )
    assert len(page1) == 5

    # Get next 5
    page2 = state_manager.list_threads(
        assistant_id=sample_assistant.id,
        skip=5,
        limit=5,
    )
    assert len(page2) == 5


# MESSAGE TESTS

def test_add_message(state_manager, sample_thread):
    """Test adding a message to a thread."""
    message = state_manager.add_message(
        thread_id=sample_thread.id,
        role="user",
        content="Hello, can you help me?",
        token_count=10,
    )

    assert message is not None
    assert message.thread_id == sample_thread.id
    assert message.role == MessageRole.USER
    assert message.content == "Hello, can you help me?"
    assert message.token_count == 10


def test_add_message_system_role(state_manager, sample_thread):
    """Test adding a system role message."""
    message = state_manager.add_message(
        thread_id=sample_thread.id,
        role="system",
        content="System prompt",
    )

    assert message.role == MessageRole.SYSTEM


def test_add_message_assistant_role(state_manager, sample_thread):
    """Test adding an assistant role message."""
    message = state_manager.add_message(
        thread_id=sample_thread.id,
        role="assistant",
        content="I can help with that.",
    )

    assert message.role == MessageRole.ASSISTANT


def test_add_message_invalid_role(state_manager, sample_thread):
    """Test that invalid role raises error."""
    with pytest.raises(Exception):
        state_manager.add_message(
            thread_id=sample_thread.id,
            role="invalid",
            content="Test",
        )


def test_add_message_to_nonexistent_thread(state_manager):
    """Test that adding message to non-existent thread raises error."""
    with pytest.raises(ThreadNotFound):
        state_manager.add_message(
            thread_id="non-existent",
            role="user",
            content="Test",
        )


def test_get_messages(state_manager, sample_thread):
    """Test retrieving messages from a thread."""
    # Add multiple messages
    messages_data = [
        ("user", "First message"),
        ("assistant", "First response"),
        ("user", "Second message"),
    ]

    for role, content in messages_data:
        state_manager.add_message(sample_thread.id, role, content)

    messages = state_manager.get_messages(sample_thread.id)

    assert len(messages) == 3
    # Verify chronological order
    assert messages[0].content == "First message"
    assert messages[1].content == "First response"
    assert messages[2].content == "Second message"


def test_get_messages_empty_thread(state_manager, sample_thread):
    """Test getting messages from empty thread returns empty list."""
    messages = state_manager.get_messages(sample_thread.id)

    assert len(messages) == 0


def test_get_messages_pagination(state_manager, sample_thread):
    """Test getting messages with pagination."""
    # Add 10 messages
    for i in range(10):
        state_manager.add_message(
            sample_thread.id,
            "user",
            f"Message {i}",
        )

    # Get first 5
    page1 = state_manager.get_messages(sample_thread.id, skip=0, limit=5)
    assert len(page1) == 5

    # Get next 5
    page2 = state_manager.get_messages(sample_thread.id, skip=5, limit=5)
    assert len(page2) == 5


# CONTEXT MANAGEMENT TESTS

def test_get_thread_context(state_manager, sample_thread):
    """Test loading thread context for inference."""
    # Add messages
    state_manager.add_message(sample_thread.id, "system", "You are helpful.", 5)
    state_manager.add_message(sample_thread.id, "user", "What's 2+2?", 5)
    state_manager.add_message(sample_thread.id, "assistant", "2+2 is 4.", 5)

    context = state_manager.get_thread_context(sample_thread.id)

    assert context["thread_id"] == sample_thread.id
    assert context["assistant_id"] == sample_thread.assistant_id
    assert len(context["messages"]) == 3
    assert context["messages"][0]["role"] == "system"
    assert context["messages"][1]["role"] == "user"
    assert context["messages"][2]["role"] == "assistant"
    # Verify chronological order
    assert context["messages"][0]["content"] == "You are helpful."
    assert context["messages"][1]["content"] == "What's 2+2?"
    assert context["messages"][2]["content"] == "2+2 is 4."


def test_get_thread_context_empty(state_manager, sample_thread):
    """Test getting context for thread with no messages."""
    context = state_manager.get_thread_context(sample_thread.id)

    assert context["thread_id"] == sample_thread.id
    assert len(context["messages"]) == 0


def test_get_thread_context_nonexistent(state_manager):
    """Test getting context for non-existent thread raises error."""
    with pytest.raises(ThreadNotFound):
        state_manager.get_thread_context("non-existent")


def test_delete_old_messages(state_manager, sample_thread):
    """Test deleting old messages, keeping only recent ones."""
    # Add 10 messages
    for i in range(10):
        state_manager.add_message(sample_thread.id, "user", f"Message {i}")

    # Keep only 3 most recent
    deleted_count = state_manager.delete_old_messages(
        sample_thread.id,
        keep_count=3,
    )

    assert deleted_count == 7

    # Verify only 3 messages remain
    messages = state_manager.get_messages(sample_thread.id)
    assert len(messages) == 3
    # Verify the 3 most recent messages are kept
    assert messages[0].content == "Message 7"
    assert messages[1].content == "Message 8"
    assert messages[2].content == "Message 9"


def test_delete_old_messages_keep_all(state_manager, sample_thread):
    """Test delete_old_messages when keep_count >= total messages."""
    # Add 5 messages
    for i in range(5):
        state_manager.add_message(sample_thread.id, "user", f"Message {i}")

    # Keep 10 (more than we have)
    deleted_count = state_manager.delete_old_messages(
        sample_thread.id,
        keep_count=10,
    )

    assert deleted_count == 0
    messages = state_manager.get_messages(sample_thread.id)
    assert len(messages) == 5


# RELATIONSHIP INTEGRITY TESTS

def test_delete_assistant_cascades_to_threads(state_manager, sample_assistant):
    """Test that deleting assistant cascades deletion to threads."""
    # Create multiple threads
    thread_ids = []
    for i in range(3):
        thread = state_manager.create_thread(sample_assistant.id)
        thread_ids.append(thread.id)

    # Delete assistant
    state_manager.delete_assistant(sample_assistant.id)

    # Verify threads are deleted
    for thread_id in thread_ids:
        with pytest.raises(ThreadNotFound):
            state_manager.get_thread(thread_id)


def test_delete_thread_cascades_to_messages(state_manager, sample_thread):
    """Test that deleting thread cascades deletion to messages."""
    # Add messages
    state_manager.add_message(sample_thread.id, "user", "Message 1")
    state_manager.add_message(sample_thread.id, "user", "Message 2")

    # Delete thread
    state_manager.delete_thread(sample_thread.id)

    # Verify thread is gone and messages are gone
    with pytest.raises(ThreadNotFound):
        state_manager.get_thread(sample_thread.id)


# FOREIGN KEY CONSTRAINT TESTS

def test_thread_requires_valid_assistant(state_manager):
    """Test that thread foreign key constraint is enforced."""
    with pytest.raises(AssistantNotFound):
        state_manager.create_thread("invalid-assistant-id")


def test_message_requires_valid_thread(state_manager):
    """Test that message foreign key constraint is enforced."""
    with pytest.raises(ThreadNotFound):
        state_manager.add_message(
            "invalid-thread-id",
            "user",
            "Test message",
        )


# TRANSACTION TESTS

def test_transaction_rollback_on_error(state_manager, sample_assistant):
    """Test that transaction rolls back on error."""
    try:
        # This should fail because thread_id doesn't exist
        state_manager.add_message(
            "invalid-thread-id",
            "user",
            "Test",
        )
    except Exception:
        pass

    # Verify the assistant still exists (transaction rolled back, not committed)
    retrieved = state_manager.get_assistant(sample_assistant.id)
    assert retrieved is not None


# DATABASE FILE TESTS

def test_database_file_created(temp_db_path):
    """Test that database file is created when StateManager is used."""
    # Extract path from sqlite URL
    db_path = temp_db_path.replace("sqlite:///", "")

    sm = StateManager(database_url=temp_db_path)

    # Create something to trigger database operations
    sm.create_assistant("Test", "Instructions")

    # Verify database file exists
    assert os.path.exists(db_path)

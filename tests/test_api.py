"""
Comprehensive API integration tests.

Tests all endpoints, request validation, response formats, and error handling.
"""

import json
import tempfile
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from database import StateManager


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.db")
    db_url = f"sqlite:///{db_path}"

    yield db_url

    # Cleanup
    sm = StateManager(database_url=db_url)
    sm.engine.dispose()
    import shutil
    try:
        shutil.rmtree(tmpdir)
    except Exception:
        pass


@pytest.fixture
def client(temp_db):
    """Create test client with temporary database."""
    # Set the database URL for testing
    import api.dependencies
    api.dependencies._state_manager = StateManager(database_url=temp_db)

    return TestClient(app)


@pytest.fixture
def sample_assistant(client):
    """Create a sample assistant for testing."""
    response = client.post(
        "/v1/assistants",
        json={
            "name": "Test Trading Bot",
            "instructions": "You are a trading analysis assistant.",
            "model": "gpt-4",
        },
        headers={"X-API-Key": "test-key"}
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def sample_thread(client, sample_assistant):
    """Create a sample thread for testing."""
    response = client.post(
        "/v1/threads",
        json={"metadata": {"test": True}},
        headers={"X-API-Key": "test-key"}
    )
    assert response.status_code == 201
    thread = response.json()

    # Update thread to associate with assistant
    import api.dependencies
    sm = api.dependencies._state_manager
    sm.update_thread(
        thread["id"],
        thread_metadata={"assistant_id": sample_assistant["id"]},
    )

    return thread


# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================

def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"
    assert "timestamp" in data


# ============================================================================
# AUTHENTICATION TESTS
# ============================================================================

def test_protected_endpoint_without_api_key(client):
    """Test that protected endpoints return 403 without API key."""
    response = client.get("/v1/assistants")
    assert response.status_code == 403
    data = response.json()
    assert "detail" in data


def test_protected_endpoint_with_correct_api_key(client):
    """Test that protected endpoints return 200 with correct API key."""
    response = client.get(
        "/v1/assistants",
        headers={"X-API-Key": "test-key"}
    )
    assert response.status_code == 200


def test_protected_endpoint_with_incorrect_api_key(client):
    """Test that protected endpoints return 401 with incorrect API key."""
    response = client.get(
        "/v1/assistants",
        headers={"X-API-Key": "wrong-key"}
    )
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data


def test_health_endpoint_public_access(client):
    """Test that health endpoint is publicly accessible without API key."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


# ============================================================================
# ASSISTANT CRUD TESTS
# ============================================================================

def test_create_assistant(client):
    """Test creating an assistant."""
    response = client.post(
        "/v1/assistants",
        json={
            "name": "Aurora Trading Bot",
            "instructions": "Analyze markets and provide trading insights.",
            "model": "gpt-4",
        },
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Aurora Trading Bot"
    assert data["instructions"] == "Analyze markets and provide trading insights."
    assert data["model"] == "gpt-4"
    assert "id" in data
    assert "created_at" in data


def test_create_assistant_invalid_data(client):
    """Test creating assistant with invalid data."""
    response = client.post(
        "/v1/assistants",
        json={
            "name": "",  # Empty name should be invalid
            "instructions": "Test",
        },
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 422


def test_get_assistant(client, sample_assistant):
    """Test getting an assistant by ID."""
    response = client.get(
        f"/v1/assistants/{sample_assistant['id']}",
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_assistant["id"]
    assert data["name"] == sample_assistant["name"]


def test_get_nonexistent_assistant(client):
    """Test getting a non-existent assistant."""
    response = client.get(
        "/v1/assistants/nonexistent",
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 404


def test_list_assistants(client):
    """Test listing assistants."""
    # Create multiple assistants
    for i in range(3):
        client.post(
            "/v1/assistants",
            json={
                "name": f"Assistant {i}",
                "instructions": f"Instructions {i}",
            },
            headers={"X-API-Key": "test-key"}
        )

    response = client.get(
        "/v1/assistants",
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3


def test_update_assistant(client, sample_assistant):
    """Test updating an assistant."""
    response = client.post(
        f"/v1/assistants/{sample_assistant['id']}",
        json={
            "name": "Updated Bot",
            "instructions": "Updated instructions",
            "model": "gpt-3.5-turbo",
        },
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Bot"
    assert data["instructions"] == "Updated instructions"


def test_delete_assistant(client, sample_assistant):
    """Test deleting an assistant."""
    response = client.delete(
        f"/v1/assistants/{sample_assistant['id']}",
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 204

    # Verify deletion
    response = client.get(
        f"/v1/assistants/{sample_assistant['id']}",
        headers={"X-API-Key": "test-key"}
    )
    assert response.status_code == 404


# ============================================================================
# THREAD TESTS
# ============================================================================

def test_create_thread(client):
    """Test creating a thread."""
    response = client.post(
        "/v1/threads",
        json={"metadata": {"user_id": "user123"}},
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "created_at" in data


def test_get_thread(client, sample_thread):
    """Test getting a thread."""
    response = client.get(
        f"/v1/threads/{sample_thread['id']}",
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_thread["id"]


def test_get_nonexistent_thread(client):
    """Test getting a non-existent thread."""
    response = client.get(
        "/v1/threads/nonexistent",
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 404


# ============================================================================
# MESSAGE TESTS
# ============================================================================

def test_add_message(client, sample_thread):
    """Test adding a message to a thread."""
    response = client.post(
        f"/v1/threads/{sample_thread['id']}/messages",
        json={
            "role": "user",
            "content": "What is the market outlook?",
        },
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "user"
    assert data["content"] == "What is the market outlook?"
    assert data["thread_id"] == sample_thread["id"]
    assert "token_count" in data


def test_add_message_invalid_role(client, sample_thread):
    """Test adding message with invalid role."""
    response = client.post(
        f"/v1/threads/{sample_thread['id']}/messages",
        json={
            "role": "invalid",
            "content": "Test",
        },
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 422


def test_add_message_empty_content(client, sample_thread):
    """Test adding message with empty content."""
    response = client.post(
        f"/v1/threads/{sample_thread['id']}/messages",
        json={
            "role": "user",
            "content": "",
        },
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 422


def test_get_messages(client, sample_thread):
    """Test getting messages from a thread."""
    # Add multiple messages
    for i in range(3):
        client.post(
            f"/v1/threads/{sample_thread['id']}/messages",
            json={
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Message {i}",
            },
            headers={"X-API-Key": "test-key"}
        )

    response = client.get(
        f"/v1/threads/{sample_thread['id']}/messages",
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    # Verify chronological order
    assert data[0]["content"] == "Message 0"
    assert data[1]["content"] == "Message 1"
    assert data[2]["content"] == "Message 2"


def test_get_messages_empty_thread(client, sample_thread):
    """Test getting messages from empty thread."""
    response = client.get(
        f"/v1/threads/{sample_thread['id']}/messages",
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


# ============================================================================
# RUN/INFERENCE TESTS
# ============================================================================

def test_create_run(client, sample_assistant, sample_thread):
    """Test creating a run (inference execution)."""
    # Add a message first
    client.post(
        f"/v1/threads/{sample_thread['id']}/messages",
        json={
            "role": "user",
            "content": "What is your analysis of the current market?",
        },
        headers={"X-API-Key": "test-key"}
    )

    # Create run
    response = client.post(
        f"/v1/threads/{sample_thread['id']}/runs",
        json={
            "assistant_id": sample_assistant["id"],
            "stream": False,
        },
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["completed", "in_progress"]
    assert data["thread_id"] == sample_thread["id"]
    assert data["assistant_id"] == sample_assistant["id"]
    assert "created_at" in data


def test_create_run_with_nonexistent_thread(client, sample_assistant):
    """Test creating run with non-existent thread."""
    response = client.post(
        "/v1/threads/nonexistent/runs",
        json={"assistant_id": sample_assistant["id"]},
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 404


def test_create_run_with_nonexistent_assistant(client, sample_thread):
    """Test creating run with non-existent assistant."""
    response = client.post(
        f"/v1/threads/{sample_thread['id']}/runs",
        json={"assistant_id": "nonexistent"},
        headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 404


def test_run_adds_response_message(client, sample_assistant, sample_thread):
    """Test that run execution adds response message to thread."""
    # Add a user message
    client.post(
        f"/v1/threads/{sample_thread['id']}/messages",
        json={
            "role": "user",
            "content": "Provide market analysis",
        },
        headers={"X-API-Key": "test-key"}
    )

    # Create run
    client.post(
        f"/v1/threads/{sample_thread['id']}/runs",
        json={"assistant_id": sample_assistant["id"]},
        headers={"X-API-Key": "test-key"}
    )

    # Get messages - should now have user + assistant response
    response = client.get(
        f"/v1/threads/{sample_thread['id']}/messages",
        headers={"X-API-Key": "test-key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["role"] == "user"
    assert data[1]["role"] == "assistant"


# ============================================================================
# WORKFLOW TESTS
# ============================================================================

def test_complete_workflow(client):
    """Test complete workflow: create assistant -> thread -> message -> run."""
    # Create assistant
    asst_resp = client.post(
        "/v1/assistants",
        json={
            "name": "Workflow Test Bot",
            "instructions": "Test assistant",
        },
        headers={"X-API-Key": "test-key"}
    )
    assert asst_resp.status_code == 201
    assistant = asst_resp.json()

    # Create thread
    thread_resp = client.post(
        "/v1/threads",
        json={},
        headers={"X-API-Key": "test-key"}
    )
    assert thread_resp.status_code == 201
    thread = thread_resp.json()

    # Add message
    msg_resp = client.post(
        f"/v1/threads/{thread['id']}/messages",
        json={
            "role": "user",
            "content": "How are the markets?",
        },
        headers={"X-API-Key": "test-key"}
    )
    assert msg_resp.status_code == 201
    message = msg_resp.json()
    assert message["role"] == "user"

    # Create run
    run_resp = client.post(
        f"/v1/threads/{thread['id']}/runs",
        json={
            "assistant_id": assistant["id"],
        },
        headers={"X-API-Key": "test-key"}
    )
    assert run_resp.status_code == 200
    run = run_resp.json()
    assert run["status"] in ["completed", "in_progress"]

    # Verify response was added
    msgs_resp = client.get(
        f"/v1/threads/{thread['id']}/messages",
        headers={"X-API-Key": "test-key"}
    )
    assert msgs_resp.status_code == 200
    messages = msgs_resp.json()
    assert len(messages) == 2
    assert messages[1]["role"] == "assistant"


# ============================================================================
# PAGINATION TESTS
# ============================================================================

def test_list_assistants_pagination(client):
    """Test pagination in list assistants."""
    # Create 10 assistants
    for i in range(10):
        client.post(
            "/v1/assistants",
            json={
                "name": f"Bot {i}",
                "instructions": f"Instructions {i}",
            },
            headers={"X-API-Key": "test-key"}
        )

    # Get first page
    response = client.get(
        "/v1/assistants?skip=0&limit=5",
        headers={"X-API-Key": "test-key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5

    # Get second page
    response = client.get(
        "/v1/assistants?skip=5&limit=5",
        headers={"X-API-Key": "test-key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 5


def test_get_messages_with_limit(client, sample_thread):
    """Test message retrieval with limit."""
    # Add 10 messages
    for i in range(10):
        client.post(
            f"/v1/threads/{sample_thread['id']}/messages",
            json={
                "role": "user",
                "content": f"Message {i}",
            },
            headers={"X-API-Key": "test-key"}
        )

    # Get limited messages
    response = client.get(
        f"/v1/threads/{sample_thread['id']}/messages?limit=5",
        headers={"X-API-Key": "test-key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5


# ============================================================================
# DOCUMENTATION TESTS
# ============================================================================

def test_openapi_schema(client):
    """Test OpenAPI schema is available."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "info" in schema
    assert "paths" in schema


def test_docs_endpoint(client):
    """Test API documentation endpoint is available."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower() or "openapi" in response.text.lower()

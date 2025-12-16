"""
Pydantic models for request and response schemas.

All models follow OpenAI API format for compatibility with Aurora TA.
"""

from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class CreateAssistantRequest(BaseModel):
    """Request schema for creating a new assistant."""

    name: str = Field(..., min_length=1, description="Assistant name")
    instructions: str = Field(
        ..., min_length=1, description="System instructions for the assistant"
    )
    model: str = Field(
        default="gpt-4", description="LLM model identifier"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional metadata"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Aurora Trading Bot",
                "instructions": "You are a trading analysis assistant specializing in technical analysis.",
                "model": "gpt-4",
                "metadata": {"version": "1.0"},
            }
        }
    }


class AssistantResponse(BaseModel):
    """Response schema for assistant objects."""

    id: str = Field(..., description="Unique assistant ID")
    name: str = Field(..., description="Assistant name")
    instructions: str = Field(..., description="System instructions")
    model: str = Field(..., description="LLM model identifier")
    created_at: int = Field(..., description="Creation timestamp (Unix)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "asst_abc123",
                "name": "Aurora Trading Bot",
                "instructions": "You are a trading analysis assistant.",
                "model": "gpt-4",
                "created_at": 1699123456,
                "metadata": None,
            }
        }
    }


class CreateThreadRequest(BaseModel):
    """Request schema for creating a new thread."""

    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional thread metadata"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "metadata": {"user_id": "user123", "session": "trading_session_1"}
            }
        }
    }


class ThreadResponse(BaseModel):
    """Response schema for thread objects."""

    id: str = Field(..., description="Unique thread ID")
    created_at: int = Field(..., description="Creation timestamp (Unix)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "thread_xyz789",
                "created_at": 1699123456,
                "metadata": {"user_id": "user123"},
            }
        }
    }


class CreateMessageRequest(BaseModel):
    """Request schema for adding a message to a thread."""

    role: Literal["user", "assistant"] = Field(
        ..., description="Message role"
    )
    content: str = Field(
        ..., min_length=1, description="Message content"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "role": "user",
                "content": "What is the current market sentiment for tech stocks?",
            }
        }
    }


class MessageResponse(BaseModel):
    """Response schema for message objects."""

    id: str = Field(..., description="Unique message ID")
    thread_id: str = Field(..., description="Parent thread ID")
    role: str = Field(..., description="Message role (system/user/assistant)")
    content: str = Field(..., description="Message content")
    created_at: int = Field(..., description="Creation timestamp (Unix)")
    token_count: Optional[int] = Field(default=None, description="Token count")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "msg_abc123",
                "thread_id": "thread_xyz789",
                "role": "user",
                "content": "What is the current market sentiment?",
                "created_at": 1699123456,
                "token_count": 12,
            }
        }
    }


class CreateRunRequest(BaseModel):
    """Request schema for executing a run (inference)."""

    assistant_id: str = Field(..., description="ID of the assistant to use")
    instructions: Optional[str] = Field(
        default=None, description="Override system instructions"
    )
    stream: bool = Field(
        default=False, description="Stream response as Server-Sent Events"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "assistant_id": "asst_abc123",
                "stream": False,
            }
        }
    }


class RunResponse(BaseModel):
    """Response schema for run objects."""

    id: str = Field(..., description="Unique run ID")
    thread_id: str = Field(..., description="Associated thread ID")
    assistant_id: str = Field(..., description="Associated assistant ID")
    status: Literal["queued", "in_progress", "completed", "failed"] = Field(
        ..., description="Run status"
    )
    created_at: int = Field(..., description="Creation timestamp (Unix)")
    completed_at: Optional[int] = Field(
        default=None, description="Completion timestamp (Unix)"
    )
    last_error: Optional[str] = Field(default=None, description="Error message if failed")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "run_def456",
                "thread_id": "thread_xyz789",
                "assistant_id": "asst_abc123",
                "status": "completed",
                "created_at": 1699123456,
                "completed_at": 1699123500,
                "last_error": None,
            }
        }
    }


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "not_found",
                "message": "Assistant not found",
                "status_code": 404,
            }
        }
    }

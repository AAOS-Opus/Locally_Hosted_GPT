"""
Thread and message management endpoints.

Handles conversation threads and messages within threads.
"""

import logging
from typing import List
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Depends

from api.models import (
    CreateThreadRequest,
    ThreadResponse,
    CreateMessageRequest,
    MessageResponse,
)
from api.dependencies import StateManagerDep
from api.auth import verify_api_key
from api.inference import MockInferenceEngine
from database import ThreadNotFound

logger = logging.getLogger(__name__)
router = APIRouter(tags=["threads"])

# Initialize inference engine for token estimation
_inference_engine = MockInferenceEngine()


@router.post(
    "",
    response_model=ThreadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Thread",
    description="Create a new conversation thread",
)
async def create_thread(
    request: CreateThreadRequest,
    state_manager: StateManagerDep,
    api_key: str = Depends(verify_api_key),
) -> ThreadResponse:
    """
    Create a new thread.

    Args:
        request: Thread creation request
        state_manager: Database state manager

    Returns:
        ThreadResponse with created thread details

    Raises:
        HTTPException: If creation fails
    """
    try:
        logger.info("Creating thread")
        # Create a temporary assistant for thread storage
        # In practice, threads don't need an assistant until inference
        # Create a default assistant if needed
        try:
            # Try to get a default assistant
            assistants = state_manager.list_assistants(limit=1)
            assistant_id = assistants[0].id if assistants else None
        except Exception:
            assistant_id = None

        # Create default assistant if none exists
        if not assistant_id:
            default_asst = state_manager.create_assistant(
                name="Default Assistant",
                instructions="Default assistant for thread operations",
            )
            assistant_id = default_asst.id

        thread = state_manager.create_thread(
            assistant_id=assistant_id,
            thread_metadata=request.metadata,
        )

        return ThreadResponse(
            id=thread.id,
            created_at=int(thread.created_at.timestamp()),
            metadata=request.metadata,
        )
    except Exception as e:
        logger.error(f"Failed to create thread: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create thread: {str(e)}",
        )


@router.get(
    "/{thread_id}",
    response_model=ThreadResponse,
    summary="Get Thread",
    description="Retrieve a thread by ID",
)
async def get_thread(
    thread_id: str,
    state_manager: StateManagerDep,
    api_key: str = Depends(verify_api_key),
) -> ThreadResponse:
    """
    Get thread by ID.

    Args:
        thread_id: ID of thread to retrieve
        state_manager: Database state manager

    Returns:
        ThreadResponse with thread details

    Raises:
        HTTPException: If thread not found
    """
    try:
        logger.debug(f"Getting thread: {thread_id}")
        thread = state_manager.get_thread(thread_id)

        return ThreadResponse(
            id=thread.id,
            created_at=int(thread.created_at.timestamp()),
            metadata=thread.thread_metadata,
        )
    except ThreadNotFound:
        logger.warning(f"Thread not found: {thread_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread not found: {thread_id}",
        )
    except Exception as e:
        logger.error(f"Error getting thread: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{thread_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Message",
    description="Add a message to a thread",
)
async def add_message(
    thread_id: str,
    request: CreateMessageRequest,
    state_manager: StateManagerDep,
    api_key: str = Depends(verify_api_key),
) -> MessageResponse:
    """
    Add a message to a thread.

    Args:
        thread_id: ID of thread to add message to
        request: Message content and role
        state_manager: Database state manager

    Returns:
        MessageResponse with message details

    Raises:
        HTTPException: If thread not found or message creation fails
    """
    try:
        logger.debug(f"Adding message to thread: {thread_id}")

        # Verify thread exists
        state_manager.get_thread(thread_id)

        # Estimate token count
        token_count = _inference_engine.estimate_tokens(request.content)

        # Add message
        message = state_manager.add_message(
            thread_id=thread_id,
            role=request.role,
            content=request.content,
            token_count=token_count,
        )

        return MessageResponse(
            id=message.id,
            thread_id=message.thread_id,
            role=message.role.value,
            content=message.content,
            created_at=int(message.timestamp.timestamp()),
            token_count=token_count,
        )
    except ThreadNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread not found: {thread_id}",
        )
    except Exception as e:
        logger.error(f"Error adding message: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/{thread_id}/messages",
    response_model=List[MessageResponse],
    summary="Get Messages",
    description="Retrieve messages from a thread",
)
async def get_messages(
    thread_id: str,
    state_manager: StateManagerDep,
    limit: int = 100,
    order: str = "asc",
    api_key: str = Depends(verify_api_key),
) -> List[MessageResponse]:
    """
    Get messages from a thread.

    Args:
        thread_id: ID of thread
        limit: Maximum messages to return
        order: Order to return messages ("asc" or "desc")
        state_manager: Database state manager

    Returns:
        List of MessageResponse objects

    Raises:
        HTTPException: If thread not found
    """
    try:
        logger.debug(f"Getting messages from thread: {thread_id}")

        # Verify thread exists
        state_manager.get_thread(thread_id)

        # Get messages
        messages = state_manager.get_messages(thread_id, limit=limit)

        # Apply ordering
        if order == "desc":
            messages = list(reversed(messages))

        return [
            MessageResponse(
                id=m.id,
                thread_id=m.thread_id,
                role=m.role.value,
                content=m.content,
                created_at=int(m.timestamp.timestamp()),
                token_count=m.token_count,
            )
            for m in messages
        ]
    except ThreadNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Thread not found: {thread_id}",
        )
    except Exception as e:
        logger.error(f"Error getting messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

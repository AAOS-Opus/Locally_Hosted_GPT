"""
Assistant management endpoints.

Handles CRUD operations for assistant configurations.
"""

import logging
from typing import List
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Depends

from api.models import CreateAssistantRequest, AssistantResponse
from api.dependencies import StateManagerDep
from api.auth import verify_api_key
from database import AssistantNotFound

logger = logging.getLogger(__name__)
router = APIRouter(tags=["assistants"])


@router.post(
    "",
    response_model=AssistantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Assistant",
    description="Create a new assistant with configuration",
)
async def create_assistant(
    request: CreateAssistantRequest,
    state_manager: StateManagerDep,
    api_key: str = Depends(verify_api_key),
) -> AssistantResponse:
    """
    Create a new assistant.

    Args:
        request: Assistant creation request with name and instructions
        state_manager: Database state manager

    Returns:
        AssistantResponse with created assistant details

    Raises:
        HTTPException: If creation fails
    """
    try:
        logger.info(f"Creating assistant: {request.name}")
        assistant = state_manager.create_assistant(
            name=request.name,
            instructions=request.instructions,
            model=request.model,
        )

        return AssistantResponse(
            id=assistant.id,
            name=assistant.name,
            instructions=assistant.instructions,
            model=assistant.model,
            created_at=int(assistant.created_at.timestamp()),
            metadata=request.metadata,
        )
    except Exception as e:
        logger.error(f"Failed to create assistant: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create assistant: {str(e)}",
        )


@router.get(
    "/{assistant_id}",
    response_model=AssistantResponse,
    summary="Get Assistant",
    description="Retrieve an assistant by ID",
)
async def get_assistant(
    assistant_id: str,
    state_manager: StateManagerDep,
    api_key: str = Depends(verify_api_key),
) -> AssistantResponse:
    """
    Get assistant by ID.

    Args:
        assistant_id: ID of assistant to retrieve
        state_manager: Database state manager

    Returns:
        AssistantResponse with assistant details

    Raises:
        HTTPException: If assistant not found
    """
    try:
        logger.debug(f"Getting assistant: {assistant_id}")
        assistant = state_manager.get_assistant(assistant_id)

        return AssistantResponse(
            id=assistant.id,
            name=assistant.name,
            instructions=assistant.instructions,
            model=assistant.model,
            created_at=int(assistant.created_at.timestamp()),
        )
    except AssistantNotFound:
        logger.warning(f"Assistant not found: {assistant_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assistant not found: {assistant_id}",
        )
    except Exception as e:
        logger.error(f"Error getting assistant: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/{assistant_id}",
    response_model=AssistantResponse,
    summary="Update Assistant",
    description="Update an existing assistant",
)
async def update_assistant(
    assistant_id: str,
    request: CreateAssistantRequest,
    state_manager: StateManagerDep,
    api_key: str = Depends(verify_api_key),
) -> AssistantResponse:
    """
    Update an assistant.

    Args:
        assistant_id: ID of assistant to update
        request: Update request with new values
        state_manager: Database state manager

    Returns:
        AssistantResponse with updated assistant details

    Raises:
        HTTPException: If assistant not found or update fails
    """
    try:
        logger.info(f"Updating assistant: {assistant_id}")
        assistant = state_manager.update_assistant(
            assistant_id,
            name=request.name,
            instructions=request.instructions,
            model=request.model,
        )

        return AssistantResponse(
            id=assistant.id,
            name=assistant.name,
            instructions=assistant.instructions,
            model=assistant.model,
            created_at=int(assistant.created_at.timestamp()),
        )
    except AssistantNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assistant not found: {assistant_id}",
        )
    except Exception as e:
        logger.error(f"Error updating assistant: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete(
    "/{assistant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Assistant",
    description="Delete an assistant and all associated data",
)
async def delete_assistant(
    assistant_id: str,
    state_manager: StateManagerDep,
    api_key: str = Depends(verify_api_key),
) -> None:
    """
    Delete an assistant.

    Args:
        assistant_id: ID of assistant to delete
        state_manager: Database state manager

    Raises:
        HTTPException: If assistant not found
    """
    try:
        logger.info(f"Deleting assistant: {assistant_id}")
        state_manager.delete_assistant(assistant_id)
    except AssistantNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assistant not found: {assistant_id}",
        )
    except Exception as e:
        logger.error(f"Error deleting assistant: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "",
    response_model=List[AssistantResponse],
    summary="List Assistants",
    description="List all assistants with optional pagination",
)
async def list_assistants(
    state_manager: StateManagerDep,
    skip: int = 0,
    limit: int = 100,
    api_key: str = Depends(verify_api_key),
) -> List[AssistantResponse]:
    """
    List assistants.

    Args:
        skip: Number of items to skip
        limit: Maximum items to return
        state_manager: Database state manager

    Returns:
        List of AssistantResponse objects
    """
    try:
        logger.debug(f"Listing assistants: skip={skip}, limit={limit}")
        assistants = state_manager.list_assistants(skip=skip, limit=limit)

        return [
            AssistantResponse(
                id=a.id,
                name=a.name,
                instructions=a.instructions,
                model=a.model,
                created_at=int(a.created_at.timestamp()),
            )
            for a in assistants
        ]
    except Exception as e:
        logger.error(f"Error listing assistants: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

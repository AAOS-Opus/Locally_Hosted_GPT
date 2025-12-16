"""
Run/inference execution endpoints.

Handles executing inference and managing run state.
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse

from api.models import CreateRunRequest, RunResponse
from api.dependencies import StateManagerDep, InferenceEngineDep
from api.auth import verify_api_key
from database import ThreadNotFound, AssistantNotFound

logger = logging.getLogger(__name__)
router = APIRouter(tags=["runs"])


@router.post(
    "/{thread_id}/runs",
    response_model=RunResponse,
    summary="Create Run",
    description="Execute inference on a thread",
)
async def create_run(
    thread_id: str,
    request: CreateRunRequest,
    state_manager: StateManagerDep,
    inference_engine: InferenceEngineDep,
    api_key: str = Depends(verify_api_key),
) -> RunResponse:
    """
    Execute inference on a thread.

    Args:
        thread_id: ID of thread to run inference on
        request: Run configuration
        state_manager: Database state manager
        inference_engine: Inference engine for generating responses

    Returns:
        RunResponse with run details and status

    Raises:
        HTTPException: If thread/assistant not found or inference fails
    """
    run_id = str(uuid.uuid4())
    created_at = datetime.utcnow()

    try:
        logger.info(f"Creating run {run_id} on thread {thread_id}")

        # Verify thread exists
        try:
            thread = state_manager.get_thread(thread_id)
        except ThreadNotFound:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Thread not found: {thread_id}",
            )

        # Verify assistant exists
        assistant_id = request.assistant_id
        try:
            assistant = state_manager.get_assistant(assistant_id)
        except AssistantNotFound:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assistant not found: {assistant_id}",
            )

        # Load thread context for inference
        context_data = state_manager.get_thread_context(thread_id)

        # Convert context to format expected by inference engine
        inference_context = context_data["messages"]

        # Run inference
        try:
            logger.debug(f"Running inference with {len(inference_context)} messages")

            response_text = await inference_engine.generate(
                context=inference_context,
                model=assistant.model,
                stream=request.stream,
            )

            # If streaming was requested, return streaming response
            if request.stream:
                async def stream_response():
                    async for chunk in response_text:
                        yield f"data: {chunk}\n\n"

                return StreamingResponse(stream_response(), media_type="text/event-stream")

            # Add response message to thread
            logger.debug("Adding assistant response to thread")
            state_manager.add_message(
                thread_id=thread_id,
                role="assistant",
                content=response_text,
                token_count=len(response_text.split()),
            )

            # Create and return run response
            completed_at = datetime.utcnow()

            return RunResponse(
                id=run_id,
                thread_id=thread_id,
                assistant_id=assistant_id,
                status="completed",
                created_at=int(created_at.timestamp()),
                completed_at=int(completed_at.timestamp()),
            )

        except Exception as e:
            logger.error(f"Inference failed: {str(e)}")

            return RunResponse(
                id=run_id,
                thread_id=thread_id,
                assistant_id=assistant_id,
                status="failed",
                created_at=int(created_at.timestamp()),
                last_error=str(e),
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Run creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

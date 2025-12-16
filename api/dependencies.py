"""
Dependency injection for FastAPI routes.

Provides StateManager and inference engine instances to route handlers.
"""

from typing import Annotated

from fastapi import Depends

from database import StateManager
from .inference import MockInferenceEngine


# Global instances (in production, these would use connection pooling)
_state_manager: StateManager = None
_inference_engine: MockInferenceEngine = None


def get_state_manager() -> StateManager:
    """
    Dependency that provides StateManager instance.

    Yields:
        StateManager instance for database operations
    """
    global _state_manager

    if _state_manager is None:
        _state_manager = StateManager()

    yield _state_manager


def get_inference_engine() -> MockInferenceEngine:
    """
    Dependency that provides inference engine instance.

    Yields:
        MockInferenceEngine instance for model inference
    """
    global _inference_engine

    if _inference_engine is None:
        _inference_engine = MockInferenceEngine()

    yield _inference_engine


# Type aliases for dependency injection
StateManagerDep = Annotated[StateManager, Depends(get_state_manager)]
InferenceEngineDep = Annotated[MockInferenceEngine, Depends(get_inference_engine)]

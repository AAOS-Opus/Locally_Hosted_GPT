"""
Dependency injection for FastAPI routes.

Provides StateManager and inference engine instances to route handlers.
"""

import os
from typing import Annotated, Union

from fastapi import Depends

from database import StateManager
from .http_inference import HttpInferenceEngine
from .inference import MockInferenceEngine


# Type alias for inference engines (both implement same interface)
InferenceEngine = Union[HttpInferenceEngine, MockInferenceEngine]

# Global instances (in production, these would use connection pooling)
_state_manager: StateManager = None
_inference_engine: InferenceEngine = None


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


def get_inference_engine() -> InferenceEngine:
    """
    Dependency that provides inference engine instance.

    Uses HttpInferenceEngine by default (routes to Sovereign Playground).
    Set USE_MOCK_INFERENCE=true to use MockInferenceEngine for testing.

    Yields:
        Inference engine instance for model inference
    """
    global _inference_engine

    if _inference_engine is None:
        use_mock = os.getenv("USE_MOCK_INFERENCE", "false").lower() == "true"

        if use_mock:
            _inference_engine = MockInferenceEngine()
        else:
            _inference_engine = HttpInferenceEngine()

    yield _inference_engine


# Type aliases for dependency injection
StateManagerDep = Annotated[StateManager, Depends(get_state_manager)]
InferenceEngineDep = Annotated[InferenceEngine, Depends(get_inference_engine)]

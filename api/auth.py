"""
API key authentication for Sovereign Assistant API.

Provides security for all /v1/* endpoints using X-API-Key header authentication.
"""

import os
import logging
from typing import Optional

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# Define the API key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Verify the provided API key against the expected key from environment.
    
    Args:
        api_key: The API key provided in the X-API-Key header
        
    Returns:
        The validated API key
        
    Raises:
        HTTPException: If the API key is invalid or missing
    """
    expected_key = os.getenv("API_KEY")
    
    if not expected_key:
        raise HTTPException(
            status_code=500,
            detail="API_KEY not configured on server"
        )
    
    if api_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    
    return api_key
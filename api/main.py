"""
Main FastAPI application for Sovereign Assistant API.

Entry point for the OpenAI-compatible REST API that Aurora TA will consume.
"""

import logging
import os
import time
from datetime import datetime
from typing import Dict, Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load environment variables from .env file BEFORE importing routes
# Routes import auth.py which reads API_KEY at module load time
load_dotenv()

from api.routes import assistants, threads, runs
from database import StateManager

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Sovereign Assistant API",
    description="OpenAI-compatible REST API for Aurora TA trading operations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add CORS middleware for web access
cors_origins = os.getenv("CORS_ORIGINS", "*")
allow_origins = cors_origins.split(",") if cors_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# LIFECYCLE EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize system on startup."""
    logger.info("=" * 70)
    logger.info("SOVEREIGN ASSISTANT API STARTUP")
    logger.info("=" * 70)
    logger.info("Initializing database and dependencies...")
    logger.info("System ready for Aurora TA requests")
    logger.info("OpenAPI documentation available at /docs")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("=" * 70)
    logger.info("SOVEREIGN ASSISTANT API SHUTDOWN")
    logger.info("=" * 70)
    logger.info("Closing database connections...")
    logger.info("System shutdown complete")


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

# Health check timeout (seconds)
HEALTH_CHECK_TIMEOUT = 3.0

# Sovereign Playground URL for health checks
SOVEREIGN_PLAYGROUND_URL = os.getenv("SOVEREIGN_PLAYGROUND_URL", "http://localhost:8080")


async def check_database() -> Dict[str, Any]:
    """
    Check database connectivity by running a simple query.

    Returns:
        Dict with status and latency
    """
    start = time.time()
    try:
        # Create a temporary StateManager to test connection
        state_manager = StateManager()
        # Run a simple query - list assistants with limit 1
        state_manager.list_assistants(limit=1)
        latency_ms = round((time.time() - start) * 1000, 2)
        return {
            "status": "healthy",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = round((time.time() - start) * 1000, 2)
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "error": str(e),
        }


async def check_sovereign_playground() -> Dict[str, Any]:
    """
    Check Sovereign Playground connectivity.

    Returns:
        Dict with status and latency
    """
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
            # Try health endpoint first, fall back to models endpoint
            response = await client.get(f"{SOVEREIGN_PLAYGROUND_URL}/health")
            latency_ms = round((time.time() - start) * 1000, 2)

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "latency_ms": latency_ms,
                    "url": SOVEREIGN_PLAYGROUND_URL,
                }
            else:
                return {
                    "status": "unhealthy",
                    "latency_ms": latency_ms,
                    "url": SOVEREIGN_PLAYGROUND_URL,
                    "error": f"HTTP {response.status_code}",
                }
    except httpx.ConnectError:
        latency_ms = round((time.time() - start) * 1000, 2)
        return {
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "url": SOVEREIGN_PLAYGROUND_URL,
            "error": "Connection refused - service may be down",
        }
    except httpx.TimeoutException:
        latency_ms = round((time.time() - start) * 1000, 2)
        return {
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "url": SOVEREIGN_PLAYGROUND_URL,
            "error": f"Timeout after {HEALTH_CHECK_TIMEOUT}s",
        }
    except Exception as e:
        latency_ms = round((time.time() - start) * 1000, 2)
        logger.error(f"Sovereign Playground health check failed: {e}")
        return {
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "url": SOVEREIGN_PLAYGROUND_URL,
            "error": str(e),
        }


@app.get("/health", summary="Health Check", description="System health status with dependency checks")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint with real dependency verification.

    Checks:
        - Database connectivity (SQLite)
        - Sovereign Playground connectivity (inference layer)

    Status logic:
        - All checks pass → "healthy"
        - Sovereign down but database works → "degraded"
        - Database down → "unhealthy"

    Returns:
        Dictionary with status, version, timestamp, and detailed checks
    """
    # Run health checks
    db_check = await check_database()
    sovereign_check = await check_sovereign_playground()

    # Determine overall status
    db_healthy = db_check["status"] == "healthy"
    sovereign_healthy = sovereign_check["status"] == "healthy"

    if db_healthy and sovereign_healthy:
        overall_status = "healthy"
    elif db_healthy and not sovereign_healthy:
        overall_status = "degraded"  # Can store, can't generate
    else:
        overall_status = "unhealthy"  # Can't function at all

    return {
        "status": overall_status,
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": db_check,
            "sovereign_playground": sovereign_check,
        },
    }


# ============================================================================
# INCLUDE ROUTERS
# ============================================================================

# Register route modules with proper prefixes
app.include_router(assistants.router, prefix="/v1/assistants")
app.include_router(threads.router, prefix="/v1/threads")
app.include_router(runs.router, prefix="/v1/threads")

logger.info("Routers registered: assistants, threads, runs")


# ============================================================================
# ERROR HANDLING
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for unexpected errors.

    Args:
        request: The request that caused the error
        exc: The exception that was raised

    Returns:
        JSON error response
    """
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred",
            "status_code": 500,
        },
    )


# OpenAPI documentation is automatically generated by FastAPI

# ============================================================================
# APPLICATION INFO
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Sovereign Assistant API...")
    logger.info("Available at: http://localhost:8000")
    logger.info("API documentation at: http://localhost:8000/docs")

    uvicorn.run(
        "api.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=True,
    )
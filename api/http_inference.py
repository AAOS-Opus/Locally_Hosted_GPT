"""
HTTP inference engine for routing to Sovereign Playground.

Calls the OpenAI-compatible chat completions endpoint at Sovereign Playground
instead of running inference locally. Supports both streaming and non-streaming.
"""

import json
import os
from typing import List, Dict, Any, AsyncGenerator, Union
import logging

import httpx

logger = logging.getLogger(__name__)

# Default timeout settings (in seconds)
DEFAULT_CONNECT_TIMEOUT = 10.0
DEFAULT_READ_TIMEOUT = 120.0  # LLM responses can take time


class HttpInferenceEngine:
    """
    HTTP-based inference engine that routes requests to Sovereign Playground.

    Provides the same interface as MockInferenceEngine, allowing seamless
    replacement in the dependency injection system.
    """

    def __init__(
        self,
        base_url: str = None,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        read_timeout: float = DEFAULT_READ_TIMEOUT,
    ):
        """
        Initialize HTTP inference engine.

        Args:
            base_url: Base URL for Sovereign Playground. If not provided,
                     reads from SOVEREIGN_PLAYGROUND_URL environment variable.
                     Defaults to http://localhost:8080 if neither is set.
            connect_timeout: Timeout for establishing connection (seconds).
            read_timeout: Timeout for reading response (seconds).
        """
        self.base_url = base_url or os.getenv(
            "SOVEREIGN_PLAYGROUND_URL", "http://localhost:8080"
        )
        # Remove trailing slash if present
        self.base_url = self.base_url.rstrip("/")

        self.timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=30.0,
            pool=10.0,
        )

        logger.info(
            f"HttpInferenceEngine initialized, routing to: {self.base_url}"
        )

    async def generate(
        self,
        context: List[Dict[str, Any]],
        model: str = "gpt-4",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Generate response by calling Sovereign Playground.

        Args:
            context: List of message dictionaries with role and content
            model: Model identifier to pass to Sovereign
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            stream: Whether to stream response

        Returns:
            Complete response string or async generator for streaming

        Raises:
            RuntimeError: If inference request fails
        """
        # Build OpenAI-compatible request payload
        payload = {
            "model": model,
            "messages": self._normalize_messages(context),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }

        endpoint = f"{self.base_url}/v1/chat/completions"

        logger.debug(
            f"Sending inference request to {endpoint} "
            f"(model={model}, stream={stream}, messages={len(context)})"
        )

        if stream:
            return self._stream_generate(endpoint, payload)
        else:
            return await self._sync_generate(endpoint, payload)

    async def _sync_generate(
        self,
        endpoint: str,
        payload: Dict[str, Any],
    ) -> str:
        """
        Non-streaming generation request.

        Args:
            endpoint: Full URL to call
            payload: Request payload

        Returns:
            Complete response text

        Raises:
            RuntimeError: If request fails
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code != 200:
                    error_text = response.text
                    logger.error(
                        f"Inference request failed: {response.status_code} - {error_text}"
                    )
                    raise RuntimeError(
                        f"Sovereign Playground returned {response.status_code}: {error_text}"
                    )

                data = response.json()

                # Extract content from OpenAI-compatible response
                content = self._extract_content(data)

                logger.debug(f"Received response ({len(content)} chars)")
                return content

        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to Sovereign Playground: {e}")
            raise RuntimeError(
                f"Cannot connect to Sovereign Playground at {self.base_url}. "
                "Is the service running?"
            ) from e
        except httpx.TimeoutException as e:
            logger.error(f"Request to Sovereign Playground timed out: {e}")
            raise RuntimeError(
                "Inference request timed out. The model may be overloaded."
            ) from e
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Sovereign Playground: {e}")
            raise RuntimeError(
                "Received invalid response from Sovereign Playground"
            ) from e

    async def _stream_generate(
        self,
        endpoint: str,
        payload: Dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        """
        Streaming generation request.

        Args:
            endpoint: Full URL to call
            payload: Request payload

        Yields:
            Response text chunks

        Raises:
            RuntimeError: If request fails
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        logger.error(
                            f"Streaming request failed: {response.status_code}"
                        )
                        raise RuntimeError(
                            f"Sovereign Playground returned {response.status_code}: "
                            f"{error_text.decode()}"
                        )

                    # Process SSE stream
                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        # SSE format: "data: {...}"
                        if line.startswith("data: "):
                            data_str = line[6:]  # Remove "data: " prefix

                            # Check for stream end marker
                            if data_str.strip() == "[DONE]":
                                logger.debug("Stream completed")
                                break

                            try:
                                data = json.loads(data_str)
                                chunk = self._extract_stream_chunk(data)
                                if chunk:
                                    yield chunk
                            except json.JSONDecodeError:
                                # Some implementations send non-JSON lines
                                logger.debug(f"Skipping non-JSON line: {line[:50]}")
                                continue

        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to Sovereign Playground: {e}")
            raise RuntimeError(
                f"Cannot connect to Sovereign Playground at {self.base_url}. "
                "Is the service running?"
            ) from e
        except httpx.TimeoutException as e:
            logger.error(f"Streaming request timed out: {e}")
            raise RuntimeError(
                "Streaming request timed out. The model may be overloaded."
            ) from e

    def _normalize_messages(
        self,
        context: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """
        Normalize message format for OpenAI-compatible API.

        Args:
            context: List of message dictionaries

        Returns:
            Normalized messages with role and content
        """
        normalized = []
        for msg in context:
            normalized.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })
        return normalized

    def _extract_content(self, data: Dict[str, Any]) -> str:
        """
        Extract content from OpenAI-compatible response.

        Args:
            data: Response JSON

        Returns:
            Message content string
        """
        try:
            # Standard OpenAI format
            choices = data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                return message.get("content", "")
            return ""
        except (KeyError, IndexError, TypeError) as e:
            logger.warning(f"Unexpected response format: {e}")
            return str(data)

    def _extract_stream_chunk(self, data: Dict[str, Any]) -> str:
        """
        Extract content from streaming chunk.

        Args:
            data: Chunk JSON

        Returns:
            Content delta string
        """
        try:
            # Standard OpenAI streaming format
            choices = data.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                return delta.get("content", "")
            return ""
        except (KeyError, IndexError, TypeError):
            return ""

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text (rough approximation).

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        # Rough estimation: ~4 characters per token
        return max(1, len(text) // 4)

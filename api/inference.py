"""
Mock inference engine for testing without GPU/vLLM.

Simulates model responses with realistic behavior. Will be replaced with
real vLLM integration on Computer 1 with GPU support.
"""

import asyncio
import random
from typing import List, Dict, Any, AsyncGenerator
import logging

logger = logging.getLogger(__name__)


class MockInferenceEngine:
    """
    Mock inference engine that simulates LLM responses.

    Provides the same interface as the real vLLM inference engine,
    allowing seamless replacement without changing other code.
    """

    # Trading-related response templates
    TRADING_TEMPLATES = [
        "Based on the current market conditions, {context} suggests a {direction} trend. Technical indicators show {indicator}, which typically {signal} a {outcome}.",
        "The price action indicates {direction} momentum. Volume analysis reveals {volume}, and moving averages are {alignment}. This points to a {recommendation}.",
        "Market sentiment is {sentiment}. Looking at support and resistance levels, a {move} would trigger {scenario}. Current RSI at {rsi} suggests the market is {condition}.",
        "Technical analysis shows {pattern} forming on the chart. If this breaks above/below {level}, we could see a move to {target}. Trading volume {volume_trend} confirms this setup.",
        "The broader trend is {direction}. In this context, {signal} is significant. Based on fibonacci levels and moving averages, {recommendation}.",
    ]

    CONTEXT_KEYWORDS = {
        "market": "the broader market environment",
        "stock": "equity price action",
        "tech": "technology sector momentum",
        "sentiment": "investor sentiment",
        "volume": "trading volume patterns",
        "trend": "the current trend",
    }

    DIRECTIONS = ["bullish", "bearish", "neutral", "consolidating"]
    INDICATORS = ["divergence in momentum", "support level bounce", "resistance breakdown", "oversold conditions"]
    SIGNALS = ["confirm", "suggest", "indicate", "provide"]
    OUTCOMES = ["short-term pullback", "strong rally", "reversal", "continuation"]
    RECOMMENDATIONS = ["consider buying on dips", "wait for confirmation", "take profits at resistance", "watch support levels"]

    def __init__(self, error_rate: float = 0.0, delay_range: tuple = (0.5, 2.0)):
        """
        Initialize mock inference engine.

        Args:
            error_rate: Probability of simulated error (0.0 to 1.0)
            delay_range: Tuple of (min, max) delay in seconds for realistic timing
        """
        self.error_rate = error_rate
        self.delay_range = delay_range
        logger.info("MockInferenceEngine initialized (development mode)")

    async def generate(
        self,
        context: List[Dict[str, Any]],
        model: str = "gpt-4",
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> str or AsyncGenerator[str, None]:
        """
        Generate response using mock inference.

        Args:
            context: List of message dictionaries with role and content
            model: Model identifier
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            stream: Whether to stream response

        Returns:
            Complete response string or async generator for streaming

        Raises:
            RuntimeError: If simulated error is triggered
        """
        # Simulate occasional errors for testing
        if random.random() < self.error_rate:
            raise RuntimeError("Simulated inference error for testing")

        # Get simulated processing delay
        delay = random.uniform(*self.delay_range)

        # Extract context from messages for better responses
        last_user_message = ""
        for msg in reversed(context):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "").lower()
                break

        # Generate contextually relevant response
        response = self._generate_contextual_response(last_user_message)

        if stream:
            return self._stream_response(response, delay)
        else:
            # Wait for processing delay
            await asyncio.sleep(delay)
            logger.debug(f"Generated response ({len(response)} chars) after {delay:.2f}s")
            return response

    async def _stream_response(
        self, response: str, delay: float
    ) -> AsyncGenerator[str, None]:
        """
        Stream response word by word.

        Args:
            response: Complete response text
            delay: Base delay between chunks

        Yields:
            Response chunks
        """
        words = response.split()
        chunk_delay = delay / len(words) if words else 0.1

        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            # Add small random variation to chunk timing
            actual_delay = chunk_delay * random.uniform(0.5, 1.5)
            await asyncio.sleep(actual_delay)

    def _generate_contextual_response(self, last_user_message: str) -> str:
        """
        Generate response contextual to user message.

        Args:
            last_user_message: The last user message content

        Returns:
            Generated response
        """
        # Check if message contains trading-related keywords
        trading_keywords = ["market", "stock", "price", "trend", "technical", "support", "resistance"]
        is_trading_query = any(kw in last_user_message for kw in trading_keywords)

        if is_trading_query:
            return self._generate_trading_response(last_user_message)
        else:
            return self._generate_generic_response(last_user_message)

    def _generate_trading_response(self, user_message: str) -> str:
        """
        Generate trading-specific response.

        Args:
            user_message: User query about trading

        Returns:
            Trading-themed response
        """
        template = random.choice(self.TRADING_TEMPLATES)

        # Extract context from user message
        context = "current market dynamics"
        for keyword, description in self.CONTEXT_KEYWORDS.items():
            if keyword in user_message:
                context = description
                break

        # Fill in template with random selections
        response = template.format(
            context=context,
            direction=random.choice(self.DIRECTIONS),
            indicator=random.choice(self.INDICATORS),
            signal=random.choice(self.SIGNALS),
            outcome=random.choice(self.OUTCOMES),
            volume="increasing" if random.random() > 0.5 else "decreasing",
            alignment="aligned with uptrend" if random.random() > 0.5 else "mixed",
            recommendation=random.choice(self.RECOMMENDATIONS),
            sentiment=random.choice(["positive", "negative", "neutral"]),
            move="upward" if random.random() > 0.5 else "downward",
            scenario="increased volatility" if random.random() > 0.5 else "consolidation",
            rsi=random.randint(30, 70),
            condition="overbought" if random.random() > 0.5 else "oversold",
            pattern="a double top" if random.random() > 0.5 else "a triple bottom",
            level=f"${random.randint(100, 500)}.{random.randint(0, 99):02d}",
            target=f"${random.randint(510, 550)}.{random.randint(0, 99):02d}",
            volume_trend="confirms" if random.random() > 0.5 else "questions",
        )

        return response

    def _generate_generic_response(self, user_message: str) -> str:
        """
        Generate generic response for non-trading queries.

        Args:
            user_message: User query

        Returns:
            Generic response
        """
        responses = [
            "I understand your question about trading. Based on current market conditions, this is a complex topic that requires careful analysis. Consider consulting with a financial advisor for specific guidance.",
            "That's an interesting question. In the context of trading systems, the answer depends on several factors including market conditions, risk tolerance, and your specific trading strategy.",
            "From a technical perspective, this relates to fundamental principles of market analysis. The relationship between these factors is important for understanding market dynamics.",
            "This is a good question that many traders ask. The key is to understand the underlying mechanics and how they interact with market conditions.",
            "Looking at this analytically, we can see several important considerations. Market behavior in this area has been studied extensively by technical analysts.",
        ]

        return random.choice(responses)

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

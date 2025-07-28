"""
AI Integration Module for Community Tip Processing.

This module handles the integration with LLM APIs to process natural language
community tips and extract structured information for health score calculation.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AIProcessorConfig(BaseModel):
    """Configuration for AI processor."""

    provider: str = "openai"  # openai, anthropic, local
    model: str = "gpt-4"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_retries: int = 3
    timeout: int = 30
    temperature: float = 0.1
    max_tokens: int = 1000


class StructuredTipData(BaseModel):
    """Structured data extracted from community tips."""

    conditions: List[str] = Field(default_factory=list)
    exclusions: List[str] = Field(default_factory=list)
    effectiveness: int = Field(
        ge=1, le=10, description="How well the tip suggests the promotion works"
    )
    confidence: int = Field(ge=1, le=10, description="Confidence in this analysis")
    sentiment: str = Field(description="Positive, negative, or neutral")
    key_phrases: List[str] = Field(default_factory=list)


class AIProcessor:
    """
    AI processor for community tip analysis.

    Integrates with LLM APIs to extract structured information from
    natural language community tips about promotions.
    """

    def __init__(self, config: Optional[AIProcessorConfig] = None):
        """Initialize AI processor with configuration."""
        self.config = config or AIProcessorConfig()
        self.client = None
        self._setup_client()

    def _setup_client(self):
        """Setup HTTP client for API calls."""
        self.client = httpx.AsyncClient(
            timeout=self.config.timeout,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )

    async def process_community_tip(
        self, tip_text: str, user_reputation: int = 50
    ) -> Dict[str, Any]:
        """
        Process a community tip through AI and return structured data.

        Args:
            tip_text: The natural language tip text
            user_reputation: User reputation score (0-100)

        Returns:
            Dictionary containing structured data and health impact
        """
        try:
            # Extract structured data using AI
            structured_data = await self._extract_structured_data(tip_text)

            # Calculate health impact based on structured data
            health_impact = self._calculate_health_impact(
                structured_data, user_reputation
            )

            # Add metadata
            result = {
                "structured_data": structured_data.dict(),
                "health_impact": health_impact,
                "processed_at": datetime.utcnow().isoformat(),
                "user_reputation": user_reputation,
                "confidence_score": structured_data.confidence / 10.0,
            }

            logger.info(
                f"Successfully processed community tip: {health_impact:.3f} impact"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to process community tip: {str(e)}")
            # Return fallback structured data
            return self._get_fallback_result(tip_text, user_reputation)

    async def _extract_structured_data(self, tip_text: str) -> StructuredTipData:
        """
        Extract structured data from tip text using LLM API.

        Args:
            tip_text: The natural language tip text

        Returns:
            StructuredTipData object
        """
        prompt = self._build_analysis_prompt(tip_text)

        for attempt in range(self.config.max_retries):
            try:
                if self.config.provider == "openai":
                    response = await self._call_openai_api(prompt)
                elif self.config.provider == "anthropic":
                    response = await self._call_anthropic_api(prompt)
                else:
                    response = await self._call_mock_api(prompt)

                # Parse and validate response
                structured_data = self._parse_ai_response(response)
                return structured_data

            except Exception as e:
                logger.warning(f"AI API call attempt {attempt + 1} failed: {str(e)}")
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(2**attempt)  # Exponential backoff

    def _build_analysis_prompt(self, tip_text: str) -> str:
        """Build the prompt for AI analysis."""
        return f"""
Analyze the following community tip about a promotion and extract structured information:

Tip: "{tip_text}"

Extract the following information in JSON format:
{{
    "conditions": [
        "List of conditions that must be met (e.g., minimum spend, specific items)"
    ],
    "exclusions": ["List of exclusions or limitations"],
    "effectiveness": <number 1-10 indicating how well the promotion works>,
    "confidence": <number 1-10 indicating your confidence in this analysis>,
    "sentiment": "<positive|negative|neutral>",
    "key_phrases": ["Important phrases or keywords from the tip"]
}}

Rules:
- effectiveness: 1=completely broken, 5=neutral, 10=works perfectly
- confidence: 1=very uncertain, 10=very confident
- Return only valid JSON, no additional text
- If unclear, use neutral values (effectiveness=5, confidence=5)
"""

    async def _call_openai_api(self, prompt: str) -> str:
        """Call OpenAI API for analysis."""
        url = f"{self.config.base_url or 'https://api.openai.com'}/v1/chat/completions"

        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert at analyzing promotion tips and extracting "
                        "structured data."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        response = await self.client.post(url, json=payload)
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def _call_anthropic_api(self, prompt: str) -> str:
        """Call Anthropic API for analysis."""
        url = f"{self.config.base_url or 'https://api.anthropic.com'}/v1/messages"

        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        response = await self.client.post(url, json=payload)
        response.raise_for_status()

        data = response.json()
        return data["content"][0]["text"]

    async def _call_mock_api(self, prompt: str) -> str:
        """Mock API call for development/testing."""
        # Simulate API delay
        await asyncio.sleep(0.1)

        # Return mock structured data
        return json.dumps(
            {
                "conditions": ["minimum $25 purchase"],
                "exclusions": ["excludes clearance items"],
                "effectiveness": 7,
                "confidence": 8,
                "sentiment": "positive",
                "key_phrases": ["works great", "20% off"],
            }
        )

    def _parse_ai_response(self, response: str) -> StructuredTipData:
        """Parse and validate AI response."""
        try:
            # Extract JSON from response
            json_str = response.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]

            data = json.loads(json_str.strip())

            # Validate and create StructuredTipData
            return StructuredTipData(
                conditions=data.get("conditions", []),
                exclusions=data.get("exclusions", []),
                effectiveness=data.get("effectiveness", 5),
                confidence=data.get("confidence", 5),
                sentiment=data.get("sentiment", "neutral"),
                key_phrases=data.get("key_phrases", []),
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse AI response: {str(e)}")
            raise ValueError(f"Invalid AI response format: {str(e)}")

    def _calculate_health_impact(
        self, structured_data: StructuredTipData, user_reputation: int
    ) -> float:
        """
        Calculate health score impact from structured data.

        Args:
            structured_data: Parsed structured data
            user_reputation: User reputation score (0-100)

        Returns:
            Health impact score (-1.0 to 1.0)
        """
        # Base impact from effectiveness (0-10 scale to -1 to 1)
        effectiveness_impact = (structured_data.effectiveness - 5) / 5.0

        # Adjust by confidence (0-10 scale to 0-1)
        confidence_multiplier = structured_data.confidence / 10.0

        # Adjust by user reputation (0-100 scale to 0.5-1.5)
        reputation_multiplier = 0.5 + (user_reputation / 100.0)

        # Sentiment adjustment
        sentiment_multiplier = {"positive": 1.2, "negative": 0.8, "neutral": 1.0}.get(
            structured_data.sentiment.lower(), 1.0
        )

        # Calculate final impact
        impact = (
            effectiveness_impact
            * confidence_multiplier
            * reputation_multiplier
            * sentiment_multiplier
        )

        # Clamp to valid range
        return max(-1.0, min(1.0, impact))

    def _get_fallback_result(
        self, tip_text: str, user_reputation: int
    ) -> Dict[str, Any]:
        """Get fallback result when AI processing fails."""
        # Handle case where tip_text might be a CommunityTip object
        if hasattr(tip_text, "tipText"):
            tip_text = tip_text.tipText
        logger.warning(f"Using fallback processing for tip: {tip_text[:50]}...")

        # Simple keyword-based fallback
        text_lower = tip_text.lower()

        # Extract conditions and exclusions
        conditions = []
        exclusions = []

        # Look for condition indicators
        if "over $" in text_lower or "minimum" in text_lower or "spend" in text_lower:
            conditions.append("Minimum spend required")
        if "sale" in text_lower:
            conditions.append("Only works on sale items")
        if "first time" in text_lower or "new customer" in text_lower:
            conditions.append("First-time customers only")

        # Look for exclusion indicators
        if "expired" in text_lower or "doesn't work" in text_lower:
            exclusions.append("Code may be expired")
        if "electronics" in text_lower:
            exclusions.append("Excludes electronics")
        if "clearance" in text_lower:
            exclusions.append("Excludes clearance items")

        # Basic sentiment analysis
        positive_words = ["works", "great", "good", "valid", "successful", "applied"]
        negative_words = ["broken", "invalid", "expired", "doesn't work", "failed"]

        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        # Base effectiveness from sentiment
        if positive_count > negative_count:
            base_effectiveness = 7
            sentiment = "positive"
        elif negative_count > positive_count:
            base_effectiveness = 3
            sentiment = "negative"
        else:
            base_effectiveness = 5
            sentiment = "neutral"

        # Adjust effectiveness based on conditions and exclusions
        effectiveness = base_effectiveness

        # Reduce effectiveness if there are exclusions
        # (restrictions make it less useful)
        if exclusions:
            effectiveness = max(1, effectiveness - 2)

        # Slightly reduce effectiveness if there are conditions
        # (requirements make it less convenient)
        if conditions:
            effectiveness = max(1, effectiveness - 1)

        fallback_data = StructuredTipData(
            conditions=conditions,
            exclusions=exclusions,
            effectiveness=effectiveness,
            confidence=5,  # Medium confidence for fallback
            sentiment=sentiment,
            key_phrases=[],
        )

        health_impact = self._calculate_health_impact(fallback_data, user_reputation)

        return {
            "structured_data": fallback_data.model_dump(),
            "health_impact": health_impact,
            "conditions": fallback_data.conditions,
            "exclusions": fallback_data.exclusions,
            "processed_at": datetime.utcnow().isoformat(),
            "user_reputation": user_reputation,
            "confidence_score": 0.3,  # Low confidence
            "fallback_used": True,
        }

    async def close(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

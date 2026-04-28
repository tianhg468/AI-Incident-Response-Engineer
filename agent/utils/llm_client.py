"""LLM client wrapper for agent nodes."""

import os
import logging
import json
from typing import Any, Optional

from anthropic import Anthropic

logger = logging.getLogger(__name__)


class LLMClient:
    """Wrapper for LLM interactions using Anthropic API.

    Provides simplified interface for agent nodes to interact with Claude.
    """

    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        """Initialize LLM client.

        Args:
            model: Model name to use
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set - LLM calls will fail")

        self.client = Anthropic(api_key=api_key) if api_key else None
        self.model = model
        logger.info(f"LLM Client initialized (model: {model})")

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs
    ) -> str:
        """Generate text from a prompt.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional arguments for the API

        Returns:
            Generated text
        """
        if not self.client:
            logger.error("LLM client not initialized - missing API key")
            return "Error: ANTHROPIC_API_KEY not set"

        try:
            messages = [{"role": "user", "content": prompt}]

            request_params = {
                "model": self.model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
                **kwargs
            }

            if system:
                request_params["system"] = system

            logger.debug(f"LLM request: {json.dumps(request_params, indent=2)}")

            response = self.client.messages.create(**request_params)

            text = response.content[0].text
            logger.debug(f"LLM response: {text}")

            return text

        except Exception as e:
            logger.error(f"Error calling LLM: {e}", exc_info=True)
            return f"Error: {str(e)}"

    def generate_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        **kwargs
    ) -> dict[str, Any]:
        """Generate structured JSON output.

        Args:
            prompt: User prompt (should request JSON output)
            system: System prompt
            max_tokens: Maximum tokens
            **kwargs: Additional arguments

        Returns:
            Parsed JSON dict
        """
        # Add instruction to return JSON
        json_prompt = f"{prompt}\n\nReturn your response as valid JSON only, with no additional text."

        response_text = self.generate(
            prompt=json_prompt,
            system=system,
            max_tokens=max_tokens,
            **kwargs
        )

        try:
            # Try to parse JSON
            # Handle markdown code blocks
            if "```json" in response_text:
                # Extract JSON from code block
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_text = response_text[start:end].strip()
            elif "```" in response_text:
                # Generic code block
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                json_text = response_text[start:end].strip()
            else:
                json_text = response_text.strip()

            return json.loads(json_text)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Response text: {response_text}")
            return {
                "error": "Failed to parse JSON response",
                "raw_response": response_text
            }

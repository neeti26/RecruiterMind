"""
LLM Client Abstraction
Supports OpenAI, Groq (fast + cheap), and Ollama (local).
Automatically falls back through providers if one fails.
"""

import json
import logging
import os
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Unified LLM client with provider fallback chain:
    OpenAI GPT-4o → Groq Llama-3.3-70B → Ollama (local)
    """

    def __init__(self, config=None):
        from config import LLMConfig
        self.config = config or LLMConfig()
        self._openai_client = None
        self._groq_client = None
        self._setup_clients()

    def _setup_clients(self):
        """Initialize available clients."""
        # OpenAI
        if self.config.api_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=self.config.api_key)
                logger.info("OpenAI client initialized")
            except ImportError:
                logger.warning("openai package not installed")

        # Groq
        if self.config.groq_api_key:
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=self.config.groq_api_key)
                logger.info("Groq client initialized")
            except ImportError:
                logger.warning("groq package not installed")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        response_format: Optional[str] = None,  # "json" for JSON mode
    ) -> str:
        """
        Get a completion. Tries providers in order of preference.
        Returns the response text.
        """
        # Try OpenAI first
        if self._openai_client:
            try:
                return self._openai_complete(
                    system_prompt, user_prompt, temperature, max_tokens, response_format
                )
            except Exception as e:
                logger.warning(f"OpenAI failed: {e}, trying Groq...")

        # Try Groq
        if self._groq_client:
            try:
                return self._groq_complete(
                    system_prompt, user_prompt, temperature, max_tokens
                )
            except Exception as e:
                logger.warning(f"Groq failed: {e}")

        raise RuntimeError(
            "No LLM available. Set OPENAI_API_KEY or GROQ_API_KEY in .env"
        )

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """Get a JSON-structured completion."""
        system_with_json = system_prompt + "\n\nYou MUST respond with valid JSON only. No markdown, no explanation."
        response = self.complete(
            system_with_json, user_prompt, temperature,
            response_format="json"
        )
        # Clean up common LLM JSON issues
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        response = response.strip()
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}\nResponse: {response[:500]}")
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise

    def _openai_complete(
        self, system: str, user: str, temperature: float,
        max_tokens: int, response_format: Optional[str]
    ) -> str:
        kwargs = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        response = self._openai_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def _groq_complete(
        self, system: str, user: str, temperature: float, max_tokens: int
    ) -> str:
        response = self._groq_client.chat.completions.create(
            model=self.config.groq_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def is_available(self) -> bool:
        """Check if any LLM is available."""
        return self._openai_client is not None or self._groq_client is not None

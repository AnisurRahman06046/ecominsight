"""
Configuration for OpenRouter API
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings


class OpenRouterConfig:
    """OpenRouter API Configuration"""

    def __init__(self):
        # OpenRouter API settings - get from main app settings
        self.api_key = settings.openrouter_api_key or ""
        self.api_base_url = "https://openrouter.ai/api/v1/chat/completions"

        # Free model on OpenRouter
        # Trying different models - Qwen is known to be good at structured tasks
        # Available free models:
        # - "qwen/qwen-2-7b-instruct:free" (7B, good at structured output)
        # - "meta-llama/llama-3.2-3b-instruct:free" (3B, smaller)
        # - "microsoft/phi-3-mini-128k-instruct:free" (3.8B)
        # - "google/gemini-2.0-flash-exp:free" (may have rate limits)

        # Using Gemini - best free model for query generation
        self.query_generation_model = "z-ai/glm-4.5-air:free"
        self.response_generation_model = "z-ai/glm-4.5-air:free"

        # API settings
        self.temperature = 0.1  # Low temperature for consistent query generation
        self.max_tokens = 1000
        self.timeout = 30  # seconds


# Global config instance
openrouter_config = OpenRouterConfig()

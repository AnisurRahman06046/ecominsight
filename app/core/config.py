"""Configuration management for the application."""

from pydantic_settings import BaseSettings
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Application settings."""

    # Server config
    app_name: str = "Ecommerce Insights Server"
    version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "ecommerce_insights"
    mongodb_max_pool_size: int = 100
    mongodb_min_pool_size: int = 10

    # Redis (for caching)
    redis_url: Optional[str] = "redis://localhost:6379"
    cache_ttl: int = 3600  # 1 hour default

    # Ollama config
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "mistral:7b-instruct"
    ollama_timeout: int = 60

    # Hugging Face models
    intent_model: str = "facebook/bart-large-mnli"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Query processing
    use_intent_classifier: bool = True
    use_template_first: bool = True
    use_rag_for_analytics: bool = True
    max_query_timeout: int = 30

    # RAG settings
    vector_db_path: str = "./data/vectordb"
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 50
    rag_top_k: int = 5

    # Performance
    enable_cache: bool = True
    max_concurrent_queries: int = 10
    batch_size: int = 32

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: Optional[str] = "logs/app.log"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
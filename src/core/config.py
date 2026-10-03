"""System configuration module using Pydantic Settings and YAML.

Provides strongly-typed hierarchical settings merging YAML definitions with
environment variable overrides.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.exceptions import ConfigurationError


def load_yaml_config(config_path: str | Path) -> dict[str, Any]:
    """Loads a YAML configuration file safely."""
    path = Path(config_path)
    if not path.exists():
        raise ConfigurationError(f"Config file not found at: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        raise ConfigurationError(f"Failed to parse YAML config at {path}: {e}") from e


class LLMConfig(BaseModel):
    cloud_model: str = "gemini-2.5-flash"
    local_model: str = "openai/llama3.2"
    embedding_model: str = "text-embedding-004"
    local_embedding_model: str = "nomic-embed-text"
    temperature: float = 0.1
    max_output_tokens: int = 2048


class AgentOrchestrationConfig(BaseModel):
    max_retry_loops: int = 3
    enable_claim_auditor: bool = True
    enable_selective_traversal: bool = True
    enable_live_update: bool = True
    timeout_seconds: int = 15


class Neo4jConfig(BaseModel):
    max_hops: int = 2
    max_traversal_nodes: int = 10


class QdrantConfig(BaseModel):
    top_k: int = 5
    score_threshold: float = 0.65


class KnowledgeConfig(BaseModel):
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)


class MemoryConfig(BaseModel):
    sqlite_db_path: str = "data/enterprise_compliance.db"
    statute_cache_ttl_hours: int = 24


class SecurityConfig(BaseModel):
    strip_zero_width_chars: bool = True
    max_input_length: int = 8000
    allowed_export_dir: str = "./workspace/dossiers"
    guarded_action_requires_token: bool = True


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "legalpilot-vn"
    APP_VERSION: str = "0.1.0"
    LOG_LEVEL: str = "INFO"

    # LLM settings
    GEMINI_API_KEY: str | None = None
    GOOGLE_CLOUD_PROJECT: str | None = None
    GOOGLE_CLOUD_LOCATION: str = "global"
    GOOGLE_GENAI_USE_VERTEXAI: bool = False

    OPENAI_API_BASE: str = "http://localhost:8000/v1"
    OPENAI_API_KEY: str = "sk-local-dummy"
    DEFAULT_MODEL: str = "gemini-2.5-flash"
    LOCAL_FALLBACK_MODEL: str = "openai/llama3.2"

    # Database settings
    SQLITE_DB_PATH: str = "data/enterprise_compliance.db"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "legalpilot2026"

    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_COLLECTION_NAME: str = "vietnamese_legal_clauses"

    # Orchestration & Security guardrails
    MAX_REFINE_LOOPS: int = 3
    MAX_RETRIEVAL_HOPS: int = 2
    MAX_DOC_TRAVERSALS: int = 5
    STATUTE_CACHE_TTL_SECONDS: int = 86400  # 24 hours
    HUMAN_GATE_REQUIRE_TOKEN: bool = True
    DOS_QUERY_TIMEOUT_SECONDS: int = 12

    # External Portals & Gazette
    VBPL_SEARCH_URL: str = "https://vbpl.vn/pages/vbpq-timkiem.aspx?Keyword={keyword}"
    VBPL_TARGET_QUERY: str | None = None

    # Nested Typed Configs
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent_orchestration: AgentOrchestrationConfig = Field(default_factory=AgentOrchestrationConfig)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    def __init__(self, **values: Any):
        super().__init__(**values)
        # Attempt to load and merge configs/system_config.yaml if present
        yaml_path = Path("configs/system_config.yaml")
        if yaml_path.exists():
            try:
                data = load_yaml_config(yaml_path)
                if "llm" in data:
                    self.llm = LLMConfig(**data["llm"])
                if "agent_orchestration" in data:
                    self.agent_orchestration = AgentOrchestrationConfig(
                        **data["agent_orchestration"]
                    )
                if "knowledge" in data:
                    self.knowledge = KnowledgeConfig(**data["knowledge"])
                if "memory" in data:
                    self.memory = MemoryConfig(**data["memory"])
                if "security" in data:
                    self.security = SecurityConfig(**data["security"])
                if "external_portals" in data:
                    portals = data["external_portals"]
                    if "vbpl_search_url" in portals:
                        self.VBPL_SEARCH_URL = portals["vbpl_search_url"]
                    if "vbpl_target_query" in portals:
                        self.VBPL_TARGET_QUERY = portals["vbpl_target_query"]
            except Exception:
                pass


# Global settings instance
settings = Settings()

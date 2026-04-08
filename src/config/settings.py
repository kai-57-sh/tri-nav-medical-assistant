"""Configuration management for TriNav application."""
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable loading."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Qwen Models
    qwen_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="Qwen API base URL"
    )
    qwen_api_key: str = Field(default="", description="Qwen API key")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", description="Redis connection URL")
    redis_session_ttl: int = Field(default=3600, description="Session TTL in seconds (60 minutes)")

    # External APIs
    amap_api_key: str | None = Field(default=None, description="Amap API key for hospital navigation")
    # Weather API configuration removed - using Open-Meteo (no auth required)
    ncbi_base_url: str = Field(
        default="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        description="NCBI E-utilities base URL"
    )

    # Observability
    langchain_tracing_v2: bool = Field(default=False, description="Enable LangSmith tracing")
    langchain_api_key: str | None = Field(default=None, description="LangSmith API key")
    langchain_project: str = Field(default="trinav-dev", description="LangSmith project name")
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None,
        description="OTLP endpoint for OpenTelemetry"
    )

    # TriNav v2 feature flags
    v2_runtime_enabled: bool = Field(default=False, description="Enable TriNav v2 runtime")
    v2_shadow_compare_enabled: bool = Field(
        default=False,
        description="Enable TriNav v2 shadow comparison"
    )
    v3_runtime_enabled: bool = Field(default=True, description="Enable TriNav v3 runtime")
    v3_shadow_compare_enabled: bool = Field(
        default=False,
        description="Enable TriNav v3 shadow comparison"
    )
    v3_legacy_fallback_enabled: bool = Field(
        default=True,
        description="Enable legacy fallback when v3 runtime primary path fails",
    )
    v3_task_coordinator_enabled: bool = Field(
        default=True,
        description="Enable v3 capability task coordinator path",
    )
    v3_builtin_plugins_enabled: bool = Field(
        default=True,
        description="Enable built-in runtime plugins in v3 parity path",
    )
    v3_plugin_trace_enabled: bool = Field(
        default=True,
        description="Enable built-in trace context plugin",
    )
    v3_plugin_medical_footer_enabled: bool = Field(
        default=True,
        description="Enable built-in medical disclaimer footer plugin",
    )
    v4_canary_enabled: bool = Field(
        default=False,
        description="Enable v4 canary rollout gate checks",
    )
    v4_gate_max_red_flag_miss_rate: float = Field(
        default=0.01,
        description="Maximum allowed red-flag miss rate before blocking rollout",
    )
    v4_gate_max_p95_ms: int = Field(
        default=6000,
        description="Maximum allowed p95 latency in milliseconds before blocking rollout",
    )

    # Server Configuration
    server_host: str = Field(default="0.0.0.0", description="Server host")
    server_port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Debug mode for development")
    log_level: str = Field(default="INFO", description="Log level")

    # Timeouts (seconds)
    llm_timeout: int = Field(default=30, description="LLM request timeout")
    amap_timeout: int = Field(default=5, description="Amap API timeout")
    # Weather timeout removed - using Open-Meteo with built-in timeout
    ncbi_timeout: int = Field(default=10, description="NCBI API timeout")

    # Constraints
    max_text_length: int = Field(default=2000, description="Max text input length")
    max_clarification_rounds: int = Field(default=2, description="Max clarification rounds")
    max_clarification_questions: int = Field(default=3, description="Max questions per turn")

    @field_validator("qwen_api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate that API key is not empty."""
        if not v or v.startswith("your_"):
            raise ValueError("QWEN_API_KEY must be set in environment variables")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()

    @field_validator("v4_gate_max_red_flag_miss_rate")
    @classmethod
    def validate_v4_gate_max_red_flag_miss_rate(cls, v: float) -> float:
        """Validate v4 canary red-flag miss-rate threshold."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("V4_GATE_MAX_RED_FLAG_MISS_RATE must be within [0, 1]")
        return v

    @field_validator("v4_gate_max_p95_ms")
    @classmethod
    def validate_v4_gate_max_p95_ms(cls, v: int) -> int:
        """Validate v4 canary latency threshold."""
        if v <= 0:
            raise ValueError("V4_GATE_MAX_P95_MS must be > 0")
        return v


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

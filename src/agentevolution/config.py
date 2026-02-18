"""AgentEvolution Configuration Management."""

from pathlib import Path
from pydantic import BaseModel, Field


class ForgeConfig(BaseModel):
    """Configuration for The Forge (tool publishing)."""
    max_code_size_bytes: int = Field(default=50_000, description="Max code size in bytes")
    max_description_length: int = Field(default=2000, description="Max description length")
    blocked_imports: list[str] = Field(
        default_factory=lambda: [
            "subprocess", "shutil", "ctypes", "multiprocessing",
            "signal", "resource", "pty", "termios",
        ],
        description="Python imports blocked for security",
    )


class GauntletConfig(BaseModel):
    """Configuration for The Gauntlet (verification)."""
    execution_timeout_seconds: int = Field(default=30, description="Max execution time")
    max_memory_mb: int = Field(default=256, description="Max memory usage in MB")
    max_output_size_bytes: int = Field(default=10_000, description="Max output size")
    allowed_network: bool = Field(default=False, description="Allow network access in sandbox")


class HiveMindConfig(BaseModel):
    """Configuration for The Hive Mind (discovery)."""
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence-transformers model for embeddings",
    )
    collection_name: str = Field(default="agentevolution_tools", description="ChromaDB collection")
    max_results: int = Field(default=10, description="Max search results")
    min_similarity: float = Field(default=0.3, description="Min cosine similarity threshold")


class FitnessConfig(BaseModel):
    """Configuration for the Fitness Engine."""
    weight_success_rate: float = 0.35
    weight_token_efficiency: float = 0.25
    weight_latency: float = 0.20
    weight_adoption: float = 0.10
    weight_freshness: float = 0.10
    decay_days: int = Field(default=30, description="Days before staleness decay begins")
    delist_threshold: float = Field(default=0.2, description="Score below which tools get delisted")


class AgentEvolutionConfig(BaseModel):
    """Root configuration for AgentEvolution."""
    data_dir: Path = Field(default=Path("./data"), description="Data directory")
    db_name: str = Field(default="agentevolution.db", description="SQLite database filename")
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8080, description="Server port")
    forge: ForgeConfig = Field(default_factory=ForgeConfig)
    gauntlet: GauntletConfig = Field(default_factory=GauntletConfig)
    hivemind: HiveMindConfig = Field(default_factory=HiveMindConfig)
    fitness: FitnessConfig = Field(default_factory=FitnessConfig)

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_name

    def ensure_dirs(self) -> None:
        """Create necessary directories."""
        self.data_dir.mkdir(parents=True, exist_ok=True)


# Global default config
_config: AgentEvolutionConfig | None = None


def get_config() -> AgentEvolutionConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = AgentEvolutionConfig()
    return _config


def set_config(config: AgentEvolutionConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config

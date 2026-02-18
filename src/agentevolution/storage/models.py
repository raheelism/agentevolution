"""AgentVerse Data Models — the core entities of the system."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum, IntEnum

from pydantic import BaseModel, Field


class TrustLevel(IntEnum):
    """Trust tiers for tools."""
    SUBMITTED = 0       # Unverified
    VERIFIED = 1        # Gauntlet-passed (sandbox verified)
    BATTLE_TESTED = 2   # 10+ successful uses by different agents
    COMMUNITY = 3       # Human-reviewed + 100+ uses


class ToolStatus(str, Enum):
    """Lifecycle status of a tool."""
    PENDING = "pending"           # Submitted, awaiting verification
    VERIFYING = "verifying"       # Currently in The Gauntlet
    ACTIVE = "active"             # Verified and available
    DEPRECATED = "deprecated"     # Manually deprecated
    DELISTED = "delisted"         # Auto-removed by fitness decay


class SecurityScanResult(str, Enum):
    """Result of security scanning."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


# ─── Tool Submission ───


class ToolSubmission(BaseModel):
    """What an agent sends when submitting a tool."""
    code: str = Field(..., description="Python source code of the tool")
    description: str = Field(..., description="What the tool does (natural language)")
    test_case: str = Field(..., description="Python code that tests the tool")
    dependencies: list[str] = Field(
        default_factory=list,
        description="Required pip packages (e.g., ['requests', 'beautifulsoup4'])",
    )
    tags: list[str] = Field(default_factory=list, description="Optional tags")
    author_agent_id: str = Field(
        default="anonymous",
        description="Identifier for the submitting agent",
    )


class ForkRequest(BaseModel):
    """Request to fork an existing tool."""
    parent_tool_id: str = Field(..., description="ID of the tool to fork")
    code: str = Field(..., description="Updated Python source code")
    description: str = Field(..., description="Updated description")
    test_case: str = Field(..., description="Updated test case")
    reason: str = Field(default="", description="Why this fork improves the original")
    author_agent_id: str = Field(default="anonymous")


# ─── Performance Profile ───


class PerformanceProfile(BaseModel):
    """Performance metrics from The Gauntlet."""
    execution_time_ms: float = 0.0
    memory_peak_mb: float = 0.0
    output_size_bytes: int = 0
    test_passed: bool = False
    test_output: str = ""
    error_message: str = ""


# ─── Provenance ───


class ProvenanceRecord(BaseModel):
    """Cryptographic provenance chain entry."""
    tool_id: str
    version: int = 1
    content_hash: str = Field(..., description="SHA-256 of the tool code")
    parent_hash: str | None = Field(None, description="Hash of parent (if forked)")
    parent_tool_id: str | None = Field(None, description="ID of parent tool (if forked)")
    author_agent_id: str = "anonymous"
    gauntlet_run_id: str = ""
    security_scan: SecurityScanResult = SecurityScanResult.PASS
    performance: PerformanceProfile = Field(default_factory=PerformanceProfile)
    signature: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─── The Tool Entity ───


class Tool(BaseModel):
    """A tool in the AgentVerse registry."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(default="", description="Auto-extracted function name")
    code: str
    description: str
    test_case: str
    dependencies: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    # Schema
    input_schema: dict = Field(default_factory=dict, description="MCP-compatible input schema")
    output_type: str = Field(default="any", description="Return type")

    # Status
    status: ToolStatus = ToolStatus.PENDING
    trust_level: TrustLevel = TrustLevel.SUBMITTED

    # Fitness
    fitness_score: float = Field(default=0.5, description="Current fitness score (0-1)")
    total_uses: int = 0
    successful_uses: int = 0
    unique_agents: int = 0

    # Provenance
    content_hash: str = ""
    parent_tool_id: str | None = None
    version: int = 1
    author_agent_id: str = "anonymous"

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: datetime | None = None

    # Performance
    avg_execution_time_ms: float = 0.0
    avg_memory_mb: float = 0.0


# ─── Usage Report ───


class UsageReport(BaseModel):
    """Agent reports tool usage outcome."""
    tool_id: str
    agent_id: str = "anonymous"
    success: bool
    execution_time_ms: float = 0.0
    error_message: str = ""
    feedback: str = ""


# ─── Recipe (Compositional Tool Chain) ───


class RecipeStep(BaseModel):
    """A single step in a recipe."""
    tool_id: str
    tool_name: str = ""
    description: str = ""
    order: int = 0


class Recipe(BaseModel):
    """A verified pipeline of tools (compositional tool chain)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    steps: list[RecipeStep]
    total_fitness: float = 0.0
    total_uses: int = 0
    successful_uses: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    author_agent_id: str = "anonymous"


# ─── API Responses ───


class ToolSummary(BaseModel):
    """Lightweight tool info for listing."""
    id: str
    name: str
    description: str
    fitness_score: float
    trust_level: TrustLevel
    status: ToolStatus
    total_uses: int
    tags: list[str]


class DiscoveryResult(BaseModel):
    """Result from semantic discovery."""
    tool: ToolSummary
    similarity_score: float
    reason: str = ""

"""AgentVerse Database — async SQLite storage for tool metadata."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from agentevolution.storage.models import (
    Recipe,
    RecipeStep,
    Tool,
    ToolStatus,
    TrustLevel,
    UsageReport,
    ProvenanceRecord,
    SecurityScanResult,
    PerformanceProfile,
)

# ─── Schema ───

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '',
    code TEXT NOT NULL,
    description TEXT NOT NULL,
    test_case TEXT NOT NULL,
    dependencies TEXT NOT NULL DEFAULT '[]',
    tags TEXT NOT NULL DEFAULT '[]',
    input_schema TEXT NOT NULL DEFAULT '{}',
    output_type TEXT NOT NULL DEFAULT 'any',
    status TEXT NOT NULL DEFAULT 'pending',
    trust_level INTEGER NOT NULL DEFAULT 0,
    fitness_score REAL NOT NULL DEFAULT 0.5,
    total_uses INTEGER NOT NULL DEFAULT 0,
    successful_uses INTEGER NOT NULL DEFAULT 0,
    unique_agents INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL DEFAULT '',
    parent_tool_id TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    author_agent_id TEXT NOT NULL DEFAULT 'anonymous',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_used_at TEXT,
    avg_execution_time_ms REAL NOT NULL DEFAULT 0.0,
    avg_memory_mb REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS usage_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id TEXT NOT NULL,
    agent_id TEXT NOT NULL DEFAULT 'anonymous',
    success BOOLEAN NOT NULL,
    execution_time_ms REAL NOT NULL DEFAULT 0.0,
    error_message TEXT NOT NULL DEFAULT '',
    feedback TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (tool_id) REFERENCES tools(id)
);

CREATE TABLE IF NOT EXISTS provenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    content_hash TEXT NOT NULL,
    parent_hash TEXT,
    parent_tool_id TEXT,
    author_agent_id TEXT NOT NULL DEFAULT 'anonymous',
    gauntlet_run_id TEXT NOT NULL DEFAULT '',
    security_scan TEXT NOT NULL DEFAULT 'pass',
    performance_json TEXT NOT NULL DEFAULT '{}',
    signature TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (tool_id) REFERENCES tools(id)
);

CREATE TABLE IF NOT EXISTS recipes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    steps_json TEXT NOT NULL DEFAULT '[]',
    total_fitness REAL NOT NULL DEFAULT 0.0,
    total_uses INTEGER NOT NULL DEFAULT 0,
    successful_uses INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    author_agent_id TEXT NOT NULL DEFAULT 'anonymous'
);

CREATE TABLE IF NOT EXISTS agent_usage (
    tool_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    use_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (tool_id, agent_id),
    FOREIGN KEY (tool_id) REFERENCES tools(id)
);

CREATE INDEX IF NOT EXISTS idx_tools_status ON tools(status);
CREATE INDEX IF NOT EXISTS idx_tools_fitness ON tools(fitness_score DESC);
CREATE INDEX IF NOT EXISTS idx_usage_tool ON usage_reports(tool_id);
CREATE INDEX IF NOT EXISTS idx_provenance_tool ON provenance(tool_id);
"""


class Database:
    """Async SQLite database for AgentVerse metadata."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Connect and initialize the database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._db

    # ─── Tools CRUD ───

    async def save_tool(self, tool: Tool) -> Tool:
        """Insert or update a tool."""
        now = datetime.now(timezone.utc).isoformat()
        tool.updated_at = datetime.now(timezone.utc)
        await self.db.execute(
            """INSERT OR REPLACE INTO tools
            (id, name, code, description, test_case, dependencies, tags,
             input_schema, output_type, status, trust_level, fitness_score,
             total_uses, successful_uses, unique_agents, content_hash,
             parent_tool_id, version, author_agent_id, created_at, updated_at,
             last_used_at, avg_execution_time_ms, avg_memory_mb)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tool.id, tool.name, tool.code, tool.description, tool.test_case,
                json.dumps(tool.dependencies), json.dumps(tool.tags),
                json.dumps(tool.input_schema), tool.output_type,
                tool.status.value, tool.trust_level.value, tool.fitness_score,
                tool.total_uses, tool.successful_uses, tool.unique_agents,
                tool.content_hash, tool.parent_tool_id, tool.version,
                tool.author_agent_id, tool.created_at.isoformat(), now,
                tool.last_used_at.isoformat() if tool.last_used_at else None,
                tool.avg_execution_time_ms, tool.avg_memory_mb,
            ),
        )
        await self.db.commit()
        return tool

    async def get_tool(self, tool_id: str) -> Tool | None:
        """Get a tool by ID."""
        async with self.db.execute("SELECT * FROM tools WHERE id = ?", (tool_id,)) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_tool(row)

    async def list_tools(
        self,
        status: ToolStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Tool]:
        """List tools ordered by fitness score."""
        if status:
            query = "SELECT * FROM tools WHERE status = ? ORDER BY fitness_score DESC LIMIT ? OFFSET ?"
            params = (status.value, limit, offset)
        else:
            query = "SELECT * FROM tools WHERE status != 'delisted' ORDER BY fitness_score DESC LIMIT ? OFFSET ?"
            params = (limit, offset)

        tools = []
        async with self.db.execute(query, params) as cursor:
            async for row in cursor:
                tools.append(self._row_to_tool(row))
        return tools

    async def update_tool_status(self, tool_id: str, status: ToolStatus) -> None:
        """Update a tool's status."""
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "UPDATE tools SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, now, tool_id),
        )
        await self.db.commit()

    async def update_tool_fitness(self, tool_id: str, fitness_score: float) -> None:
        """Update a tool's fitness score."""
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "UPDATE tools SET fitness_score = ?, updated_at = ? WHERE id = ?",
            (fitness_score, now, tool_id),
        )
        await self.db.commit()

    async def update_tool_trust(self, tool_id: str, trust_level: TrustLevel) -> None:
        """Update a tool's trust level."""
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "UPDATE tools SET trust_level = ?, updated_at = ? WHERE id = ?",
            (trust_level.value, now, tool_id),
        )
        await self.db.commit()

    # ─── Usage ───

    async def record_usage(self, report: UsageReport) -> None:
        """Record a usage report and update tool stats."""
        now = datetime.now(timezone.utc).isoformat()

        # Insert usage report
        await self.db.execute(
            """INSERT INTO usage_reports (tool_id, agent_id, success, execution_time_ms,
               error_message, feedback, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (report.tool_id, report.agent_id, report.success,
             report.execution_time_ms, report.error_message, report.feedback, now),
        )

        # Update tool usage stats
        if report.success:
            await self.db.execute(
                """UPDATE tools SET
                    total_uses = total_uses + 1,
                    successful_uses = successful_uses + 1,
                    last_used_at = ?,
                    updated_at = ?
                WHERE id = ?""",
                (now, now, report.tool_id),
            )
        else:
            await self.db.execute(
                """UPDATE tools SET
                    total_uses = total_uses + 1,
                    last_used_at = ?,
                    updated_at = ?
                WHERE id = ?""",
                (now, now, report.tool_id),
            )

        # Track unique agents
        await self.db.execute(
            """INSERT INTO agent_usage (tool_id, agent_id, use_count)
            VALUES (?, ?, 1)
            ON CONFLICT(tool_id, agent_id) DO UPDATE SET use_count = use_count + 1""",
            (report.tool_id, report.agent_id),
        )

        # Update unique agent count
        async with self.db.execute(
            "SELECT COUNT(DISTINCT agent_id) FROM agent_usage WHERE tool_id = ?",
            (report.tool_id,),
        ) as cursor:
            row = await cursor.fetchone()
            unique_count = row[0] if row else 0

        await self.db.execute(
            "UPDATE tools SET unique_agents = ? WHERE id = ?",
            (unique_count, report.tool_id),
        )

        await self.db.commit()

    # ─── Provenance ───

    async def save_provenance(self, record: ProvenanceRecord) -> None:
        """Save a provenance record."""
        await self.db.execute(
            """INSERT INTO provenance
            (tool_id, version, content_hash, parent_hash, parent_tool_id,
             author_agent_id, gauntlet_run_id, security_scan, performance_json,
             signature, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.tool_id, record.version, record.content_hash,
                record.parent_hash, record.parent_tool_id,
                record.author_agent_id, record.gauntlet_run_id,
                record.security_scan.value,
                record.performance.model_dump_json(),
                record.signature, record.created_at.isoformat(),
            ),
        )
        await self.db.commit()

    async def get_provenance_chain(self, tool_id: str) -> list[ProvenanceRecord]:
        """Get full provenance chain for a tool."""
        records = []
        async with self.db.execute(
            "SELECT * FROM provenance WHERE tool_id = ? ORDER BY version ASC",
            (tool_id,),
        ) as cursor:
            async for row in cursor:
                records.append(ProvenanceRecord(
                    tool_id=row["tool_id"],
                    version=row["version"],
                    content_hash=row["content_hash"],
                    parent_hash=row["parent_hash"],
                    parent_tool_id=row["parent_tool_id"],
                    author_agent_id=row["author_agent_id"],
                    gauntlet_run_id=row["gauntlet_run_id"],
                    security_scan=SecurityScanResult(row["security_scan"]),
                    performance=PerformanceProfile.model_validate_json(row["performance_json"]),
                    signature=row["signature"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                ))
        return records

    # ─── Recipes ───

    async def save_recipe(self, recipe: Recipe) -> Recipe:
        """Save a recipe."""
        await self.db.execute(
            """INSERT OR REPLACE INTO recipes
            (id, name, description, steps_json, total_fitness,
             total_uses, successful_uses, created_at, author_agent_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                recipe.id, recipe.name, recipe.description,
                json.dumps([s.model_dump() for s in recipe.steps]),
                recipe.total_fitness, recipe.total_uses, recipe.successful_uses,
                recipe.created_at.isoformat(), recipe.author_agent_id,
            ),
        )
        await self.db.commit()
        return recipe

    async def list_recipes(self, limit: int = 20) -> list[Recipe]:
        """List recipes ordered by fitness."""
        recipes = []
        async with self.db.execute(
            "SELECT * FROM recipes ORDER BY total_fitness DESC LIMIT ?", (limit,)
        ) as cursor:
            async for row in cursor:
                steps = [RecipeStep(**s) for s in json.loads(row["steps_json"])]
                recipes.append(Recipe(
                    id=row["id"], name=row["name"], description=row["description"],
                    steps=steps, total_fitness=row["total_fitness"],
                    total_uses=row["total_uses"], successful_uses=row["successful_uses"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    author_agent_id=row["author_agent_id"],
                ))
        return recipes

    # ─── Helpers ───

    def _row_to_tool(self, row: aiosqlite.Row) -> Tool:
        """Convert a DB row to a Tool object."""
        return Tool(
            id=row["id"], name=row["name"], code=row["code"],
            description=row["description"], test_case=row["test_case"],
            dependencies=json.loads(row["dependencies"]),
            tags=json.loads(row["tags"]),
            input_schema=json.loads(row["input_schema"]),
            output_type=row["output_type"],
            status=ToolStatus(row["status"]),
            trust_level=TrustLevel(row["trust_level"]),
            fitness_score=row["fitness_score"],
            total_uses=row["total_uses"],
            successful_uses=row["successful_uses"],
            unique_agents=row["unique_agents"],
            content_hash=row["content_hash"],
            parent_tool_id=row["parent_tool_id"],
            version=row["version"],
            author_agent_id=row["author_agent_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_used_at=datetime.fromisoformat(row["last_used_at"]) if row["last_used_at"] else None,
            avg_execution_time_ms=row["avg_execution_time_ms"],
            avg_memory_mb=row["avg_memory_mb"],
        )

"""Tool Discovery — Semantic search with intent-aware matching.

Goes beyond simple keyword matching by understanding what
an agent is trying to accomplish.
"""

from __future__ import annotations

from agentevolution.storage.database import Database
from agentevolution.storage.vector_store import VectorStore
from agentevolution.storage.models import DiscoveryResult, ToolSummary, ToolStatus, Tool


class Discovery:
    """The Hive Mind's discovery engine.

    Provides semantic tool search with fitness-weighted ranking.
    """

    def __init__(self, db: Database, vector_store: VectorStore):
        self.db = db
        self.vector_store = vector_store

    async def search(
        self,
        query: str,
        max_results: int = 10,
        min_similarity: float = 0.3,
        min_trust_level: int = 0,
    ) -> list[DiscoveryResult]:
        """Search for tools matching a natural language intent.

        Combines semantic similarity with fitness scoring to return
        the best tools for the job.
        """
        # Get semantic matches from vector store
        results = self.vector_store.search(
            query=query,
            max_results=max_results * 2,  # Over-fetch for filtering
            min_similarity=min_similarity,
        )

        # Enrich with full tool data and filter
        enriched: list[DiscoveryResult] = []
        for result in results:
            tool = await self.db.get_tool(result.tool.id)
            if tool is None:
                continue
            if tool.trust_level < min_trust_level:
                continue
            if tool.status != ToolStatus.ACTIVE:
                continue

            # Update with full data
            result.tool = ToolSummary(
                id=tool.id,
                name=tool.name,
                description=tool.description,
                fitness_score=tool.fitness_score,
                trust_level=tool.trust_level,
                status=tool.status,
                total_uses=tool.total_uses,
                tags=tool.tags,
            )

            enriched.append(result)

        # Re-rank by composite score
        enriched.sort(
            key=lambda r: self._composite_score(r),
            reverse=True,
        )

        return enriched[:max_results]

    async def get_tool_details(self, tool_id: str) -> Tool | None:
        """Get full details of a specific tool."""
        return await self.db.get_tool(tool_id)

    async def list_tools(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ToolSummary]:
        """List all active tools ordered by fitness."""
        tools = await self.db.list_tools(
            status=ToolStatus.ACTIVE, limit=limit, offset=offset,
        )
        return [
            ToolSummary(
                id=t.id, name=t.name, description=t.description,
                fitness_score=t.fitness_score, trust_level=t.trust_level,
                status=t.status, total_uses=t.total_uses, tags=t.tags,
            )
            for t in tools
        ]

    def _composite_score(self, result: DiscoveryResult) -> float:
        """Calculate composite ranking score.

        Balances semantic relevance with tool quality.
        """
        similarity = result.similarity_score
        fitness = result.tool.fitness_score
        trust_bonus = result.tool.trust_level * 0.05

        return (
            0.50 * similarity +
            0.35 * fitness +
            0.15 * trust_bonus
        )

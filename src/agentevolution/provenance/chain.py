"""Provenance Chain — Git-like version history for tools."""

from __future__ import annotations

import uuid

from agentevolution.storage.database import Database
from agentevolution.storage.models import (
    ProvenanceRecord,
    Tool,
    PerformanceProfile,
    SecurityScanResult,
)
from agentevolution.utils.hashing import hash_code, sign_tool


class ProvenanceManager:
    """Manages the cryptographic provenance chain for tools.

    Every tool version gets a content-addressable hash and links
    back to its parent, creating a Git-like version tree.
    """

    def __init__(self, db: Database):
        self.db = db

    async def create_record(
        self,
        tool: Tool,
        performance: PerformanceProfile,
        security_result: SecurityScanResult,
        parent_hash: str | None = None,
    ) -> ProvenanceRecord:
        """Create and save a provenance record for a tool."""
        gauntlet_run_id = str(uuid.uuid4())
        content_hash = hash_code(tool.code)
        signature = sign_tool(content_hash, gauntlet_run_id)

        record = ProvenanceRecord(
            tool_id=tool.id,
            version=tool.version,
            content_hash=content_hash,
            parent_hash=parent_hash,
            parent_tool_id=tool.parent_tool_id,
            author_agent_id=tool.author_agent_id,
            gauntlet_run_id=gauntlet_run_id,
            security_scan=security_result,
            performance=performance,
            signature=signature,
        )

        await self.db.save_provenance(record)
        return record

    async def get_chain(self, tool_id: str) -> list[ProvenanceRecord]:
        """Get the full provenance chain for a tool."""
        return await self.db.get_provenance_chain(tool_id)

    async def get_lineage(self, tool_id: str) -> list[ProvenanceRecord]:
        """Trace the full lineage through forks.

        Follows parent_tool_id links to build the complete
        ancestry tree.
        """
        lineage: list[ProvenanceRecord] = []
        current_id = tool_id

        while current_id:
            chain = await self.db.get_provenance_chain(current_id)
            lineage.extend(chain)

            # Find parent tool
            tool = await self.db.get_tool(current_id)
            current_id = tool.parent_tool_id if tool else None

        return list(reversed(lineage))

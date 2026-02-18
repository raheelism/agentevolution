"""Trust System — Automatic trust tier promotion.

Tools earn trust through verified usage:
  Level 0: Submitted (unverified)
  Level 1: Gauntlet-verified
  Level 2: Battle-tested (10+ agents)
  Level 3: Community-audited (100+ uses)
"""

from __future__ import annotations

from agentevolution.storage.database import Database
from agentevolution.storage.models import Tool, TrustLevel


class TrustManager:
    """Manages automatic trust tier promotions."""

    def __init__(self, db: Database):
        self.db = db

    async def evaluate_trust(self, tool: Tool) -> TrustLevel:
        """Evaluate and potentially promote a tool's trust level.

        Trust levels are monotonically increasing — once earned,
        they don't go down (status/fitness handles quality control).
        """
        current = tool.trust_level

        if current < TrustLevel.VERIFIED:
            # Can't auto-promote to verified — Gauntlet does that
            return current

        if current < TrustLevel.BATTLE_TESTED:
            if tool.unique_agents >= 10 and tool.successful_uses >= 20:
                await self.db.update_tool_trust(tool.id, TrustLevel.BATTLE_TESTED)
                return TrustLevel.BATTLE_TESTED

        if current < TrustLevel.COMMUNITY:
            if tool.unique_agents >= 50 and tool.successful_uses >= 100:
                await self.db.update_tool_trust(tool.id, TrustLevel.COMMUNITY)
                return TrustLevel.COMMUNITY

        return current

"""Fitness Scorer — Evolutionary scoring for tools.

Tools compete for survival based on real-world usage.
The best tools rise, stale tools decay and get delisted.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from agentevolution.config import get_config
from agentevolution.storage.models import Tool


class FitnessScorer:
    """Calculates evolutionary fitness scores for tools.

    fitness = (
        w1 * success_rate +
        w2 * token_efficiency +
        w3 * (1 - latency_norm) +
        w4 * adoption_velocity +
        w5 * freshness
    )
    """

    def __init__(self):
        config = get_config().fitness
        self.w_success = config.weight_success_rate
        self.w_token_eff = config.weight_token_efficiency
        self.w_latency = config.weight_latency
        self.w_adoption = config.weight_adoption
        self.w_freshness = config.weight_freshness
        self.decay_days = config.decay_days
        self.delist_threshold = config.delist_threshold

    def calculate(self, tool: Tool) -> float:
        """Calculate the fitness score for a tool."""
        success_rate = self._success_rate(tool)
        token_efficiency = self._token_efficiency(tool)
        latency_score = self._latency_score(tool)
        adoption = self._adoption_velocity(tool)
        freshness = self._freshness(tool)

        score = (
            self.w_success * success_rate +
            self.w_token_eff * token_efficiency +
            self.w_latency * latency_score +
            self.w_adoption * adoption +
            self.w_freshness * freshness
        )

        return round(max(0.0, min(1.0, score)), 4)

    def should_delist(self, tool: Tool) -> bool:
        """Check if a tool should be delisted due to low fitness."""
        score = self.calculate(tool)
        return score < self.delist_threshold and tool.total_uses >= 5

    def _success_rate(self, tool: Tool) -> float:
        """Ratio of successful to total uses."""
        if tool.total_uses == 0:
            return 0.5  # Neutral for unused tools
        return tool.successful_uses / tool.total_uses

    def _token_efficiency(self, tool: Tool) -> float:
        """Proxy for token cost savings.

        Based on code size — smaller, focused tools are more efficient.
        Normalized: 100 chars = 1.0, 10000+ chars = 0.1
        """
        code_len = len(tool.code)
        if code_len <= 100:
            return 1.0
        elif code_len >= 10000:
            return 0.1
        return 1.0 - (0.9 * (code_len - 100) / 9900)

    def _latency_score(self, tool: Tool) -> float:
        """Inverse of execution time. Faster = better.

        Score:
          < 100ms  → 1.0
          < 1000ms → 0.7
          < 5000ms → 0.4
          > 5000ms → 0.1
        """
        ms = tool.avg_execution_time_ms
        if ms <= 0:
            return 0.5  # Unknown
        elif ms < 100:
            return 1.0
        elif ms < 1000:
            return 0.7
        elif ms < 5000:
            return 0.4
        else:
            return 0.1

    def _adoption_velocity(self, tool: Tool) -> float:
        """How many unique agents have adopted this tool.

        Uses logarithmic scaling: log2(unique_agents + 1) / log2(100)
        """
        if tool.unique_agents <= 0:
            return 0.0
        return min(1.0, math.log2(tool.unique_agents + 1) / math.log2(100))

    def _freshness(self, tool: Tool) -> float:
        """How recently has the tool been used.

        Decays after decay_days of inactivity.
        """
        if tool.last_used_at is None:
            # Never used — check creation date
            ref_date = tool.created_at
        else:
            ref_date = tool.last_used_at

        now = datetime.now(timezone.utc)
        days_inactive = (now - ref_date).total_seconds() / 86400

        if days_inactive <= self.decay_days:
            return 1.0

        # Exponential decay after threshold
        excess_days = days_inactive - self.decay_days
        return max(0.0, math.exp(-0.05 * excess_days))

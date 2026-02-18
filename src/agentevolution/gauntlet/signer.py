"""Cryptographic Signer — Sign verified tools."""

from agentevolution.utils.hashing import sign_tool


class Signer:
    """Signs tools after they pass The Gauntlet."""

    def sign(self, content_hash: str, gauntlet_run_id: str) -> str:
        """Create a signature for a verified tool.

        In production, this would use asymmetric keys.
        MVP uses HMAC-like combination.
        """
        return sign_tool(content_hash, gauntlet_run_id)

    def verify(self, content_hash: str, gauntlet_run_id: str, signature: str) -> bool:
        """Verify a tool's signature."""
        expected = sign_tool(content_hash, gauntlet_run_id)
        return expected == signature

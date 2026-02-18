"""Content-addressable hashing for tool provenance."""

import hashlib


def hash_code(code: str) -> str:
    """Generate SHA-256 hash of code content.

    This creates a content-addressable identifier for tool code,
    similar to how Git hashes file content.
    """
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def hash_tool(code: str, description: str, test_case: str) -> str:
    """Generate a composite hash of a tool's defining content.

    Includes code, description, and test case to create a unique
    fingerprint for each version of a tool.
    """
    composite = f"{code}\n---DESC---\n{description}\n---TEST---\n{test_case}"
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()


def sign_tool(content_hash: str, gauntlet_run_id: str) -> str:
    """Create a simple signature combining content hash and gauntlet run.

    In production, this would use asymmetric cryptography.
    For MVP, we use HMAC-like combination.
    """
    payload = f"{content_hash}:{gauntlet_run_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

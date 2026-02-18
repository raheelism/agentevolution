"""Code Normalizer — Clean and standardize submitted code."""

from __future__ import annotations

import ast
import textwrap


def normalize_code(code: str) -> str:
    """Normalize submitted code for consistency.

    - Strips leading/trailing whitespace
    - Dedents code
    - Validates it parses as valid Python
    - Ensures consistent formatting
    """
    code = textwrap.dedent(code).strip()

    # Validate it's parseable Python
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Invalid Python code: {e}") from e

    return code


def extract_function_name(code: str) -> str:
    """Extract the primary function name from code.

    Returns the name of the first function/class found.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return "unknown_tool"

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
        elif isinstance(node, ast.ClassDef):
            return node.name

    return "unknown_tool"


def validate_code_size(code: str, max_bytes: int = 50_000) -> None:
    """Validate code doesn't exceed size limits."""
    size = len(code.encode("utf-8"))
    if size > max_bytes:
        raise ValueError(
            f"Code size ({size} bytes) exceeds maximum ({max_bytes} bytes)"
        )

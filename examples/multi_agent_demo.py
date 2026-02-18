"""
AgentEvolution Multi-Agent Demo
════════════════════════════

Simulates 3 agents building on each other's work:

  🤖 Agent Alpha    → Builds text utility tools
  🤖 Agent Beta     → Discovers and uses Alpha's tools, builds data tools
  🤖 Agent Gamma    → Forks Alpha's tool with improvements, reports usage

This populates the dashboard with real tools and activity.

Run: python examples/multi_agent_demo.py
Then open: http://localhost:8080 (dashboard)
"""

import asyncio
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentevolution.config import AgentEvolutionConfig, set_config
from agentevolution.server import AgentEvolutionApp
from agentevolution.storage.models import ToolSubmission, ForkRequest, UsageReport, TrustLevel


# ─── Tool Definitions ───

TOOLS = [
    # Agent Alpha's tools
    {
        "agent": "agent-alpha",
        "submission": ToolSubmission(
            code='''
def slugify(text: str) -> str:
    """Convert text to URL-friendly slug.

    Args:
        text: Input text to slugify

    Returns:
        URL-safe slug string
    """
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\\w\\s-]', '', text)
    text = re.sub(r'[\\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text
''',
            description="Convert any text to a clean, URL-friendly slug. Handles special characters, whitespace, and edge cases.",
            test_case='''
result = slugify("Hello World! This is a Test")
assert result == "hello-world-this-is-a-test", f"Got: {result}"

result = slugify("  Multiple   Spaces  ")
assert result == "multiple-spaces", f"Got: {result}"

result = slugify("Special @#$ Characters!")
assert result == "special-characters", f"Got: {result}"
''',
            tags=["string", "url", "text", "utility"],
            author_agent_id="agent-alpha",
        ),
    },
    {
        "agent": "agent-alpha",
        "submission": ToolSubmission(
            code='''
def extract_emails(text: str) -> list:
    """Extract all email addresses from text.

    Args:
        text: Input text containing emails

    Returns:
        List of email addresses found
    """
    import re
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}'
    return re.findall(pattern, text)
''',
            description="Extract all valid email addresses from any text string. Uses RFC-compliant regex pattern matching.",
            test_case='''
result = extract_emails("Contact us at hello@example.com or support@test.org")
assert len(result) == 2
assert "hello@example.com" in result
assert "support@test.org" in result

result = extract_emails("no emails here")
assert result == []
''',
            tags=["email", "extraction", "regex", "text"],
            author_agent_id="agent-alpha",
        ),
    },
    {
        "agent": "agent-alpha",
        "submission": ToolSubmission(
            code='''
def word_frequency(text: str, top_n: int = 10) -> dict:
    """Count word frequency in text, returning top N words.

    Args:
        text: Input text to analyze
        top_n: Number of top words to return

    Returns:
        Dict mapping words to their counts
    """
    import re
    from collections import Counter
    words = re.findall(r'\\b[a-zA-Z]+\\b', text.lower())
    stop_words = {'the', 'a', 'an', 'is', 'in', 'it', 'of', 'and', 'to', 'for', 'on', 'with', 'as', 'at', 'by'}
    words = [w for w in words if w not in stop_words and len(w) > 2]
    counts = Counter(words)
    return dict(counts.most_common(top_n))
''',
            description="Analyze word frequency in text. Returns top N most common words with counts, excluding common stop words.",
            test_case='''
result = word_frequency("the quick brown fox jumps over the lazy dog fox fox")
assert "fox" in result
assert result["fox"] == 3

result = word_frequency("hello hello world", top_n=1)
assert len(result) == 1
assert "hello" in result
''',
            tags=["nlp", "text", "analysis", "frequency"],
            author_agent_id="agent-alpha",
        ),
    },
    # Agent Beta's tools
    {
        "agent": "agent-beta",
        "submission": ToolSubmission(
            code='''
def csv_to_json(csv_string: str) -> list:
    """Convert CSV string to list of dictionaries.

    Args:
        csv_string: CSV formatted string with header row

    Returns:
        List of dicts, one per row
    """
    lines = csv_string.strip().split('\\n')
    if len(lines) < 2:
        return []
    headers = [h.strip() for h in lines[0].split(',')]
    result = []
    for line in lines[1:]:
        values = [v.strip() for v in line.split(',')]
        row = dict(zip(headers, values))
        result.append(row)
    return result
''',
            description="Convert CSV formatted strings to structured JSON (list of dictionaries). Handles headers automatically.",
            test_case='''
csv = "name,age,city\\nAlice,30,NYC\\nBob,25,LA"
result = csv_to_json(csv)
assert len(result) == 2
assert result[0]["name"] == "Alice"
assert result[1]["city"] == "LA"
''',
            tags=["csv", "json", "data", "conversion"],
            author_agent_id="agent-beta",
        ),
    },
    {
        "agent": "agent-beta",
        "submission": ToolSubmission(
            code='''
def flatten_dict(d: dict, parent_key: str = '', sep: str = '.') -> dict:
    """Flatten a nested dictionary.

    Args:
        d: Nested dictionary to flatten
        parent_key: Prefix for keys (used in recursion)
        sep: Separator between key levels

    Returns:
        Flat dictionary with dotted keys
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)
''',
            description="Flatten deeply nested dictionaries into flat key-value pairs using dot notation. Essential for working with JSON APIs and configs.",
            test_case='''
result = flatten_dict({"a": 1, "b": {"c": 2, "d": {"e": 3}}})
assert result == {"a": 1, "b.c": 2, "b.d.e": 3}

result = flatten_dict({})
assert result == {}
''',
            tags=["dict", "json", "flatten", "utility"],
            author_agent_id="agent-beta",
        ),
    },
    {
        "agent": "agent-beta",
        "submission": ToolSubmission(
            code='''
def validate_json_schema(data: dict, schema: dict) -> dict:
    """Simple JSON schema validator.

    Args:
        data: Data to validate
        schema: Schema with 'required' and 'types' fields

    Returns:
        Dict with 'valid' bool and 'errors' list
    """
    errors = []
    required = schema.get('required', [])
    types = schema.get('types', {})

    for field in required:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    for field, expected_type in types.items():
        if field in data:
            type_map = {'string': str, 'integer': int, 'float': float, 'boolean': bool, 'list': list, 'dict': dict}
            expected = type_map.get(expected_type)
            if expected and not isinstance(data[field], expected):
                errors.append(f"Field '{field}' expected {expected_type}, got {type(data[field]).__name__}")

    return {'valid': len(errors) == 0, 'errors': errors}
''',
            description="Lightweight JSON schema validator. Checks required fields and type constraints without external dependencies.",
            test_case='''
schema = {"required": ["name", "age"], "types": {"name": "string", "age": "integer"}}
result = validate_json_schema({"name": "Alice", "age": 30}, schema)
assert result["valid"] == True

result = validate_json_schema({"name": "Alice"}, schema)
assert result["valid"] == False
assert len(result["errors"]) == 1
''',
            tags=["validation", "schema", "json", "data"],
            author_agent_id="agent-beta",
        ),
    },
]

# Agent Gamma's fork
FORK = {
    "agent": "agent-gamma",
    "will_fork_index": 0,  # Fork the slugify tool
    "fork": ForkRequest(
        parent_tool_id="",  # Will be filled dynamically
        code='''
def slugify(text: str, max_length: int = 80) -> str:
    """Convert text to URL-friendly slug with length limit.

    Enhanced version with:
    - Unicode transliteration support
    - Maximum length enforcement
    - Better edge case handling

    Args:
        text: Input text to slugify
        max_length: Maximum slug length (default 80)

    Returns:
        URL-safe slug string
    """
    import re
    import unicodedata
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = text.lower().strip()
    text = re.sub(r'[^\\w\\s-]', '', text)
    text = re.sub(r'[\\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    if len(text) > max_length:
        text = text[:max_length].rsplit('-', 1)[0]
    return text
''',
        description="Enhanced slugify with Unicode transliteration, configurable max length, and better edge case handling. Fork of original slugify.",
        test_case='''
result = slugify("Hello World! This is a Test")
assert result == "hello-world-this-is-a-test", f"Got: {result}"

result = slugify("Café résumé naïve")
assert "cafe" in result

result = slugify("A very long title " * 10, max_length=20)
assert len(result) <= 20
''',
        reason="Added Unicode transliteration and max_length support",
        author_agent_id="agent-gamma",
    ),
}

# Usage reports from different agents
USAGE_REPORTS = [
    {"tool_index": 0, "agent": "agent-beta", "success": True, "time_ms": 3.5},
    {"tool_index": 0, "agent": "agent-gamma", "success": True, "time_ms": 4.2},
    {"tool_index": 0, "agent": "agent-delta", "success": True, "time_ms": 2.8},
    {"tool_index": 1, "agent": "agent-gamma", "success": True, "time_ms": 8.1},
    {"tool_index": 1, "agent": "agent-delta", "success": True, "time_ms": 7.5},
    {"tool_index": 2, "agent": "agent-beta", "success": True, "time_ms": 15.2},
    {"tool_index": 3, "agent": "agent-alpha", "success": True, "time_ms": 5.0},
    {"tool_index": 3, "agent": "agent-gamma", "success": True, "time_ms": 5.5},
    {"tool_index": 4, "agent": "agent-alpha", "success": True, "time_ms": 1.2},
    {"tool_index": 5, "agent": "agent-alpha", "success": True, "time_ms": 12.0},
    {"tool_index": 5, "agent": "agent-delta", "success": False, "time_ms": 0, "error": "Invalid schema format"},
]


async def main():
    print("=" * 60)
    print("  AgentEvolution — Multi-Agent Demo")
    print("  3 agents building on each other's work")
    print("=" * 60)

    config = AgentEvolutionConfig()
    set_config(config)
    app = AgentEvolutionApp(config)
    await app.start()

    try:
        created_tools = []

        # ─── Phase 1: Agents submit tools ───
        print("\n--- Phase 1: Tool Submissions ---\n")

        for i, tool_def in enumerate(TOOLS):
            agent = tool_def["agent"]
            sub = tool_def["submission"]

            tool = await app.forge.submit_tool(sub)

            # Run through Gauntlet
            security = app.scanner.scan(tool.code)
            sandbox_result = app.sandbox.execute(tool.code, tool.test_case)

            status = "PASS" if sandbox_result.success else "FAIL"
            print(f"  [{agent}] {tool.name:30s} Security: {security.result.value:4s} | Sandbox: {status} | {sandbox_result.execution_time_ms:.0f}ms")

            if sandbox_result.success and security.passed:
                perf = sandbox_result.to_performance_profile()
                await app.provenance.create_record(tool, perf, security.result)
                tool = await app.forge.activate_tool(tool)
                await app.db.update_tool_trust(tool.id, TrustLevel.VERIFIED)
                tool.avg_execution_time_ms = sandbox_result.execution_time_ms
                await app.db.save_tool(tool)

            created_tools.append(tool)
            await asyncio.sleep(0.3)  # Stagger for timestamps

        # ─── Phase 2: Agent Gamma forks a tool ───
        print("\n--- Phase 2: Agent Gamma Forks slugify ---\n")

        parent_tool = created_tools[FORK["will_fork_index"]]
        FORK["fork"].parent_tool_id = parent_tool.id

        forked_tool = await app.forge.fork_tool(FORK["fork"])
        security = app.scanner.scan(forked_tool.code)
        sandbox_result = app.sandbox.execute(forked_tool.code, forked_tool.test_case)

        print(f"  [agent-gamma] Forked '{parent_tool.name}' -> '{forked_tool.name}' v{forked_tool.version}")
        print(f"               Security: {security.result.value} | Sandbox: {'PASS' if sandbox_result.success else 'FAIL'}")

        if sandbox_result.success and security.passed:
            perf = sandbox_result.to_performance_profile()
            await app.provenance.create_record(forked_tool, perf, security.result, parent_hash=parent_tool.content_hash)
            forked_tool = await app.forge.activate_tool(forked_tool)
            await app.db.update_tool_trust(forked_tool.id, TrustLevel.VERIFIED)
            created_tools.append(forked_tool)

        # ─── Phase 3: Usage Reports ───
        print("\n--- Phase 3: Usage Reports (Cross-Agent Adoption) ---\n")

        for report_def in USAGE_REPORTS:
            tool = created_tools[report_def["tool_index"]]
            report = UsageReport(
                tool_id=tool.id,
                agent_id=report_def["agent"],
                success=report_def["success"],
                execution_time_ms=report_def.get("time_ms", 0),
                error_message=report_def.get("error", ""),
            )
            await app.db.record_usage(report)

            # Update fitness
            updated = await app.db.get_tool(tool.id)
            new_fitness = app.fitness.calculate(updated)
            await app.db.update_tool_fitness(tool.id, new_fitness)

            icon = "+" if report_def["success"] else "x"
            print(f"  [{icon}] {report_def['agent']:15s} used {tool.name:30s} -> fitness: {new_fitness:.4f}")

        # ─── Phase 4: Discovery ───
        print("\n--- Phase 4: Semantic Discovery ---\n")

        queries = [
            "I need to parse CSV data into structured format",
            "how to clean text for URLs",
            "validate data against a schema",
            "analyze word distribution in documents",
        ]

        for query in queries:
            results = await app.discovery.search(query, max_results=3)
            if results:
                top = results[0]
                print(f'  Q: "{query}"')
                print(f'  A: {top.tool.name} (similarity: {top.similarity_score:.0%}, fitness: {top.tool.fitness_score:.2f})')
                print()
            else:
                print(f'  Q: "{query}" -> No results\n')

        # ─── Summary ───
        print("=" * 60)
        print("  Demo complete! Dashboard data populated.")
        print(f"  Tools created: {len(created_tools)}")
        print(f"  Usage reports: {len(USAGE_REPORTS)}")
        print()
        print("  Start the dashboard to see it visually:")
        print("    python -m agentevolution.dashboard.app")
        print("    Then open: http://localhost:8080")
        print("=" * 60)

    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())

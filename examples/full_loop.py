"""
AgentEvolution Example: Full Loop Demo
═══════════════════════════════════

Demonstrates the complete AgentEvolution cycle:
  1. Agent A submits a tool
  2. Tool passes the Gauntlet (auto-verified)
  3. Agent B discovers the tool
  4. Agent B uses it and reports success
  5. Fitness score updates

Run: python examples/full_loop.py
"""

import asyncio
import json
from pathlib import Path

# Add src to path for direct execution
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agentevolution.config import AgentEvolutionConfig, set_config
from agentevolution.server import AgentEvolutionApp
from agentevolution.storage.models import ToolSubmission, UsageReport


async def main():
    print("🔥 AgentEvolution — Full Loop Demo")
    print("=" * 50)

    # Initialize with temp data dir
    config = AgentEvolutionConfig(data_dir=Path("./demo_data"))
    set_config(config)
    app = AgentEvolutionApp(config)
    await app.start()

    try:
        # ─── Step 1: Agent A submits a tool ───
        print("\n📦 Step 1: Agent A submits a tool...")

        submission = ToolSubmission(
            code='''
def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert temperature from Celsius to Fahrenheit.

    Args:
        celsius: Temperature in Celsius

    Returns:
        Temperature in Fahrenheit
    """
    return (celsius * 9/5) + 32
''',
            description="Convert temperature from Celsius to Fahrenheit. Accurate unit conversion utility.",
            test_case='''
result = celsius_to_fahrenheit(100)
assert result == 212, f"Expected 212, got {result}"

result = celsius_to_fahrenheit(0)
assert result == 32, f"Expected 32, got {result}"

result = celsius_to_fahrenheit(-40)
assert result == -40, f"Expected -40, got {result}"
''',
            tags=["temperature", "conversion", "utility"],
            author_agent_id="agent-alpha",
        )

        tool = await app.forge.submit_tool(submission)
        print(f"   Tool created: {tool.name} ({tool.id[:8]}...)")

        # ─── Step 2: Gauntlet Verification ───
        print("\n🗡️ Step 2: Running through The Gauntlet...")

        # Security scan
        security = app.scanner.scan(tool.code)
        print(f"   Security: {security.result.value} ({len(security.issues)} issues)")

        # Sandbox execution
        sandbox_result = app.sandbox.execute(tool.code, tool.test_case)
        print(f"   Sandbox: {'✅ PASS' if sandbox_result.success else '❌ FAIL'}")
        print(f"   Execution time: {sandbox_result.execution_time_ms:.0f}ms")

        if sandbox_result.success:
            # Activate the tool
            from agentevolution.storage.models import TrustLevel
            tool = await app.forge.activate_tool(tool)
            await app.db.update_tool_trust(tool.id, TrustLevel.VERIFIED)
            print(f"   Status: ACTIVE ✅")

            # Create provenance
            perf = sandbox_result.to_performance_profile()
            prov = await app.provenance.create_record(tool, perf, security.result)
            print(f"   Provenance hash: {prov.content_hash[:16]}...")
            print(f"   Signature: {prov.signature}")
        else:
            print(f"   ❌ Tool rejected: {sandbox_result.error_message}")
            return

        # ─── Step 3: Agent B discovers the tool ───
        print("\n🧠 Step 3: Agent B searches for a tool...")

        results = await app.discovery.search("convert temperature celsius fahrenheit")
        if results:
            found = results[0]
            print(f"   Found: {found.tool.name}")
            print(f"   Similarity: {found.similarity_score:.2%}")
            print(f"   Fitness: {found.tool.fitness_score:.2f}")
        else:
            print("   No results (embeddings may need initial indexing)")

        # ─── Step 4: Agent B reports usage ───
        print("\n📊 Step 4: Agent B uses the tool and reports success...")

        report = UsageReport(
            tool_id=tool.id,
            agent_id="agent-beta",
            success=True,
            execution_time_ms=5.0,
        )
        await app.db.record_usage(report)

        # Recalculate fitness
        updated_tool = await app.db.get_tool(tool.id)
        new_fitness = app.fitness.calculate(updated_tool)
        await app.db.update_tool_fitness(tool.id, new_fitness)

        print(f"   New fitness score: {new_fitness:.4f}")
        print(f"   Total uses: {updated_tool.total_uses}")
        print(f"   Unique agents: {updated_tool.unique_agents}")

        # ─── Summary ───
        print("\n" + "=" * 50)
        print("🎉 Full loop complete!")
        print(f"   Tool '{tool.name}' is now live in AgentEvolution")
        print(f"   Any agent can discover it by asking:")
        print(f'   "I need to convert temperature units"')

    finally:
        await app.stop()
        # Cleanup demo data
        import shutil
        if Path("./demo_data").exists():
            try:
                shutil.rmtree("./demo_data")
                print("\n🧹 Demo data cleaned up")
            except PermissionError:
                print("\n⚠️  Could not fully clean demo_data (file locks). Remove manually.")


if __name__ == "__main__":
    asyncio.run(main())

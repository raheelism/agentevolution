"""
AgentEvolution — The Self-Evolving MCP Tool Ecosystem
══════════════════════════════════════════════════════

Main MCP Server that exposes 7 tool endpoints:

  🔨 FORGE:
    • submit_tool    — Agent publishes a new tool
    • fork_tool      — Agent improves an existing tool

  🗡️ GAUNTLET:      (runs automatically on submission)

  🧠 HIVE MIND:
    • discover_tool  — Semantic search by intent
    • get_recipe     — Get a pre-verified tool chain
    • list_tools     — Browse available tools

  📊 LIFECYCLE:
    • report_usage   — Report success/failure
    • get_tool       — Get a specific tool's details

Usage:
    agentevolution             # Start the server
    python -m agentevolution   # Alternative start
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool as MCPTool,
)

from agentevolution.config import AgentEvolutionConfig, get_config, set_config
from agentevolution.forge.publisher import Forge
from agentevolution.gauntlet.sandbox import Sandbox
from agentevolution.gauntlet.security import SecurityScanner
from agentevolution.gauntlet.signer import Signer
from agentevolution.hivemind.discovery import Discovery
from agentevolution.hivemind.recipes import RecipeEngine
from agentevolution.fitness.scorer import FitnessScorer
from agentevolution.provenance.chain import ProvenanceManager
from agentevolution.provenance.trust import TrustManager
from agentevolution.storage.database import Database
from agentevolution.storage.vector_store import VectorStore
from agentevolution.storage.models import (
    ForkRequest,
    ToolSubmission,
    ToolStatus,
    TrustLevel,
    UsageReport,
)

# ─── Logging ───

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("agentevolution")


# ─── Application State ───

class AgentEvolutionApp:
    """Application container holding all subsystems."""

    def __init__(self, config: AgentEvolutionConfig | None = None):
        if config:
            set_config(config)
        self.config = get_config()

        # Storage
        self.db = Database(self.config.db_path)
        self.vector_store = VectorStore(
            self.config.data_dir,
            self.config.hivemind.collection_name,
        )

        # Core systems
        self.forge = Forge(self.db, self.vector_store)
        self.sandbox = Sandbox()
        self.scanner = SecurityScanner()
        self.signer = Signer()
        self.discovery = Discovery(self.db, self.vector_store)
        self.recipes = RecipeEngine(self.db)
        self.fitness = FitnessScorer()
        self.provenance = ProvenanceManager(self.db)
        self.trust = TrustManager(self.db)

    async def start(self) -> None:
        """Initialize all subsystems."""
        self.config.ensure_dirs()
        await self.db.connect()
        self.vector_store.connect()
        logger.info("🚀 AgentEvolution initialized — data: %s", self.config.data_dir)

    async def stop(self) -> None:
        """Shutdown all subsystems."""
        await self.db.close()
        logger.info("👋 AgentEvolution stopped")


# ─── MCP Server Definition ───

def create_server() -> tuple[Server, AgentEvolutionApp]:
    """Create the MCP server with all tool endpoints."""

    server = Server("agentevolution")
    app = AgentEvolutionApp()

    # ─── Tool Definitions ───

    @server.list_tools()
    async def handle_list_tools() -> list[MCPTool]:
        """Return all available MCP tool endpoints."""
        return [
            MCPTool(
                name="submit_tool",
                description=(
                    "Submit a new tool to AgentEvolution. The tool will be automatically "
                    "verified in a sandbox before being made available to other agents."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python source code of the tool function",
                        },
                        "description": {
                            "type": "string",
                            "description": "What this tool does (natural language)",
                        },
                        "test_case": {
                            "type": "string",
                            "description": "Python code that tests the tool (should use assert)",
                        },
                        "dependencies": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Required pip packages",
                            "default": [],
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional tags for categorization",
                            "default": [],
                        },
                        "author_agent_id": {
                            "type": "string",
                            "description": "Your agent identifier",
                            "default": "anonymous",
                        },
                    },
                    "required": ["code", "description", "test_case"],
                },
            ),
            MCPTool(
                name="fork_tool",
                description=(
                    "Fork an existing tool to create an improved version. "
                    "The new tool will maintain provenance linking back to the original."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "parent_tool_id": {
                            "type": "string",
                            "description": "ID of the tool to fork",
                        },
                        "code": {
                            "type": "string",
                            "description": "Updated Python source code",
                        },
                        "description": {
                            "type": "string",
                            "description": "Updated description",
                        },
                        "test_case": {
                            "type": "string",
                            "description": "Updated test case",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Why this fork improves the original",
                            "default": "",
                        },
                    },
                    "required": ["parent_tool_id", "code", "description", "test_case"],
                },
            ),
            MCPTool(
                name="discover_tool",
                description=(
                    "Search for tools by describing what you need in natural language. "
                    "Returns the best matching tools ranked by relevance and fitness."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language description of what you need",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            ),
            MCPTool(
                name="get_tool",
                description="Get full details of a specific tool by its ID.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tool_id": {
                            "type": "string",
                            "description": "The tool's unique ID",
                        },
                    },
                    "required": ["tool_id"],
                },
            ),
            MCPTool(
                name="list_available_tools",
                description="List all active tools in the registry, ordered by fitness score.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of tools to return",
                            "default": 20,
                        },
                    },
                },
            ),
            MCPTool(
                name="report_usage",
                description=(
                    "Report the outcome of using a tool. This feeds the fitness engine "
                    "and helps the best tools rise to the top."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "tool_id": {
                            "type": "string",
                            "description": "ID of the tool that was used",
                        },
                        "success": {
                            "type": "boolean",
                            "description": "Whether the tool worked correctly",
                        },
                        "execution_time_ms": {
                            "type": "number",
                            "description": "How long execution took in milliseconds",
                            "default": 0,
                        },
                        "error_message": {
                            "type": "string",
                            "description": "Error message if the tool failed",
                            "default": "",
                        },
                        "agent_id": {
                            "type": "string",
                            "description": "Your agent identifier",
                            "default": "anonymous",
                        },
                    },
                    "required": ["tool_id", "success"],
                },
            ),
            MCPTool(
                name="get_recipe",
                description=(
                    "Get a pre-verified tool chain (recipe) for complex multi-step tasks. "
                    "Recipes are pipelines of tools that work together."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of recipes to return",
                            "default": 10,
                        },
                    },
                },
            ),
        ]

    # ─── Tool Handlers ───

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Route tool calls to the appropriate handler."""
        try:
            if name == "submit_tool":
                return await _handle_submit(app, arguments)
            elif name == "fork_tool":
                return await _handle_fork(app, arguments)
            elif name == "discover_tool":
                return await _handle_discover(app, arguments)
            elif name == "get_tool":
                return await _handle_get_tool(app, arguments)
            elif name == "list_available_tools":
                return await _handle_list(app, arguments)
            elif name == "report_usage":
                return await _handle_report_usage(app, arguments)
            elif name == "get_recipe":
                return await _handle_get_recipe(app, arguments)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as e:
            logger.error("Error in %s: %s", name, e, exc_info=True)
            return [TextContent(type="text", text=f"Error: {type(e).__name__}: {str(e)}")]

    return server, app


# ─── Tool Handler Implementations ───


async def _handle_submit(app: AgentEvolutionApp, args: dict) -> list[TextContent]:
    """Handle submit_tool: Agent publishes a new tool."""
    submission = ToolSubmission(
        code=args["code"],
        description=args["description"],
        test_case=args["test_case"],
        dependencies=args.get("dependencies", []),
        tags=args.get("tags", []),
        author_agent_id=args.get("author_agent_id", "anonymous"),
    )

    # Step 1: Submit to Forge
    tool = await app.forge.submit_tool(submission)
    logger.info("📦 Tool submitted: %s (%s)", tool.name, tool.id)

    # Step 2: Security scan
    security_report = app.scanner.scan(tool.code)
    if not security_report.passed:
        await app.db.update_tool_status(tool.id, ToolStatus.DELISTED)
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "rejected",
                "reason": "security_scan_failed",
                "details": security_report.summary(),
                "tool_id": tool.id,
            }, indent=2),
        )]

    logger.info("🔒 Security scan passed for %s", tool.name)

    # Step 3: Sandbox verification
    sandbox_result = app.sandbox.execute(tool.code, tool.test_case)
    performance = sandbox_result.to_performance_profile()

    if not sandbox_result.success:
        await app.db.update_tool_status(tool.id, ToolStatus.DELISTED)
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "rejected",
                "reason": "test_failed",
                "details": sandbox_result.error_message,
                "stdout": sandbox_result.stdout[:500],
                "stderr": sandbox_result.stderr[:500],
                "tool_id": tool.id,
            }, indent=2),
        )]

    logger.info("✅ Sandbox verification passed for %s (%.0fms)", tool.name, sandbox_result.execution_time_ms)

    # Step 4: Create provenance record
    provenance = await app.provenance.create_record(
        tool=tool,
        performance=performance,
        security_result=security_report.result,
    )

    # Step 5: Activate the tool
    tool = await app.forge.activate_tool(tool)
    tool.trust_level = TrustLevel.VERIFIED
    tool.avg_execution_time_ms = sandbox_result.execution_time_ms
    await app.db.save_tool(tool)
    await app.db.update_tool_trust(tool.id, TrustLevel.VERIFIED)

    logger.info("🎉 Tool activated: %s (%s) — fitness: %.2f", tool.name, tool.id, tool.fitness_score)

    return [TextContent(
        type="text",
        text=json.dumps({
            "status": "active",
            "tool_id": tool.id,
            "name": tool.name,
            "fitness_score": tool.fitness_score,
            "trust_level": "verified",
            "content_hash": provenance.content_hash[:16] + "...",
            "execution_time_ms": sandbox_result.execution_time_ms,
            "message": f"🎉 Tool '{tool.name}' is now live in AgentEvolution!",
        }, indent=2),
    )]


async def _handle_fork(app: AgentEvolutionApp, args: dict) -> list[TextContent]:
    """Handle fork_tool: Agent improves an existing tool."""
    request = ForkRequest(
        parent_tool_id=args["parent_tool_id"],
        code=args["code"],
        description=args["description"],
        test_case=args["test_case"],
        reason=args.get("reason", ""),
        author_agent_id=args.get("author_agent_id", "anonymous"),
    )

    # Fork in The Forge
    tool = await app.forge.fork_tool(request)

    # Run through Gauntlet (same as submit)
    security_report = app.scanner.scan(tool.code)
    if not security_report.passed:
        await app.db.update_tool_status(tool.id, ToolStatus.DELISTED)
        return [TextContent(type="text", text=json.dumps({
            "status": "rejected",
            "reason": "security_scan_failed",
            "details": security_report.summary(),
        }, indent=2))]

    sandbox_result = app.sandbox.execute(tool.code, tool.test_case)
    if not sandbox_result.success:
        await app.db.update_tool_status(tool.id, ToolStatus.DELISTED)
        return [TextContent(type="text", text=json.dumps({
            "status": "rejected",
            "reason": "test_failed",
            "details": sandbox_result.error_message,
        }, indent=2))]

    # Create provenance with parent link
    parent = await app.db.get_tool(request.parent_tool_id)
    parent_hash = parent.content_hash if parent else None
    performance = sandbox_result.to_performance_profile()

    await app.provenance.create_record(
        tool=tool,
        performance=performance,
        security_result=security_report.result,
        parent_hash=parent_hash,
    )

    # Activate
    tool = await app.forge.activate_tool(tool)
    await app.db.update_tool_trust(tool.id, TrustLevel.VERIFIED)

    return [TextContent(type="text", text=json.dumps({
        "status": "active",
        "tool_id": tool.id,
        "name": tool.name,
        "forked_from": request.parent_tool_id,
        "version": tool.version,
        "message": f"🔀 Fork of '{parent.name if parent else 'unknown'}' is now live!",
    }, indent=2))]


async def _handle_discover(app: AgentEvolutionApp, args: dict) -> list[TextContent]:
    """Handle discover_tool: Semantic search for tools."""
    query = args["query"]
    max_results = args.get("max_results", 5)

    results = await app.discovery.search(query, max_results=max_results)

    if not results:
        return [TextContent(type="text", text=json.dumps({
            "results": [],
            "message": "No matching tools found. You could build one and submit it!",
        }, indent=2))]

    output = {
        "results": [
            {
                "tool_id": r.tool.id,
                "name": r.tool.name,
                "description": r.tool.description,
                "fitness_score": r.tool.fitness_score,
                "trust_level": r.tool.trust_level,
                "similarity": r.similarity_score,
                "total_uses": r.tool.total_uses,
            }
            for r in results
        ],
        "total": len(results),
    }

    return [TextContent(type="text", text=json.dumps(output, indent=2))]


async def _handle_get_tool(app: AgentEvolutionApp, args: dict) -> list[TextContent]:
    """Handle get_tool: Get full tool details."""
    tool = await app.db.get_tool(args["tool_id"])
    if tool is None:
        return [TextContent(type="text", text=json.dumps({
            "error": "Tool not found",
            "tool_id": args["tool_id"],
        }))]

    return [TextContent(type="text", text=json.dumps({
        "id": tool.id,
        "name": tool.name,
        "description": tool.description,
        "code": tool.code,
        "test_case": tool.test_case,
        "input_schema": tool.input_schema,
        "status": tool.status.value,
        "trust_level": tool.trust_level.value,
        "fitness_score": tool.fitness_score,
        "total_uses": tool.total_uses,
        "successful_uses": tool.successful_uses,
        "tags": tool.tags,
        "version": tool.version,
        "parent_tool_id": tool.parent_tool_id,
        "content_hash": tool.content_hash,
        "created_at": tool.created_at.isoformat(),
    }, indent=2))]


async def _handle_list(app: AgentEvolutionApp, args: dict) -> list[TextContent]:
    """Handle list_available_tools: Browse the registry."""
    limit = args.get("limit", 20)
    summaries = await app.discovery.list_tools(limit=limit)

    return [TextContent(type="text", text=json.dumps({
        "tools": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description[:100],
                "fitness_score": s.fitness_score,
                "trust_level": s.trust_level,
                "total_uses": s.total_uses,
                "tags": s.tags,
            }
            for s in summaries
        ],
        "total": len(summaries),
    }, indent=2))]


async def _handle_report_usage(app: AgentEvolutionApp, args: dict) -> list[TextContent]:
    """Handle report_usage: Feed the fitness engine."""
    report = UsageReport(
        tool_id=args["tool_id"],
        agent_id=args.get("agent_id", "anonymous"),
        success=args["success"],
        execution_time_ms=args.get("execution_time_ms", 0),
        error_message=args.get("error_message", ""),
    )

    # Record the usage
    await app.db.record_usage(report)

    # Recalculate fitness
    tool = await app.db.get_tool(report.tool_id)
    if tool:
        new_fitness = app.fitness.calculate(tool)
        await app.db.update_tool_fitness(tool.id, new_fitness)

        # Check for trust promotion
        tool.fitness_score = new_fitness
        new_trust = await app.trust.evaluate_trust(tool)

        # Check for delisting
        if app.fitness.should_delist(tool):
            await app.forge.delist_tool(tool.id)
            logger.warning("💀 Tool delisted due to low fitness: %s", tool.name)

        return [TextContent(type="text", text=json.dumps({
            "recorded": True,
            "tool_id": tool.id,
            "new_fitness_score": new_fitness,
            "trust_level": new_trust.value,
            "total_uses": tool.total_uses + 1,
        }, indent=2))]

    return [TextContent(type="text", text=json.dumps({
        "error": "Tool not found",
        "tool_id": args["tool_id"],
    }))]


async def _handle_get_recipe(app: AgentEvolutionApp, args: dict) -> list[TextContent]:
    """Handle get_recipe: List available recipes."""
    limit = args.get("limit", 10)
    recipes = await app.recipes.list_recipes(limit=limit)

    return [TextContent(type="text", text=json.dumps({
        "recipes": [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "steps": [
                    {"tool_id": s.tool_id, "tool_name": s.tool_name, "order": s.order}
                    for s in r.steps
                ],
                "total_fitness": r.total_fitness,
                "total_uses": r.total_uses,
            }
            for r in recipes
        ],
    }, indent=2))]


# ─── Entry Point ───

async def run_server() -> None:
    """Run the AgentEvolution MCP server."""
    server, app = create_server()

    await app.start()

    try:
        async with stdio_server() as (read_stream, write_stream):
            logger.info("🌐 AgentEvolution MCP server running via stdio")
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        await app.stop()


def main() -> None:
    """CLI entry point."""
    print("🔥 AgentEvolution — The Self-Evolving MCP Tool Ecosystem", file=sys.stderr)
    print("   Starting server...", file=sys.stderr)
    asyncio.run(run_server())


if __name__ == "__main__":
    main()

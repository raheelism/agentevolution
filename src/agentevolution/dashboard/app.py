"""AgentEvolution Dashboard — FastAPI backend serving the web UI.

Provides REST API endpoints and serves the static dashboard.
Run: agentevolution-dashboard (or python -m agentevolution.dashboard.app)
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agentevolution.config import AgentEvolutionConfig, get_config, set_config
from agentevolution.storage.database import Database
from agentevolution.storage.vector_store import VectorStore
from agentevolution.fitness.scorer import FitnessScorer
from agentevolution.storage.models import ToolStatus

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("agentevolution.dashboard")

# ─── Static files path ─── 
STATIC_DIR = Path(__file__).parent / "static"

# ─── App State ───

db: Database | None = None
vector_store: VectorStore | None = None
fitness: FitnessScorer | None = None


def create_app() -> FastAPI:
    """Create the FastAPI dashboard application."""
    app = FastAPI(
        title="AgentEvolution Dashboard",
        description="The Self-Evolving MCP Tool Ecosystem — Visual Dashboard",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ─── Lifecycle ───

    @app.on_event("startup")
    async def startup():
        global db, vector_store, fitness
        config = get_config()
        config.ensure_dirs()
        db = Database(config.db_path)
        await db.connect()
        vector_store = VectorStore(config.data_dir, config.hivemind.collection_name)
        vector_store.connect()
        fitness = FitnessScorer()
        logger.info("🖥️  Dashboard connected to AgentEvolution data at %s", config.data_dir)

    @app.on_event("shutdown")
    async def shutdown():
        if db:
            await db.close()

    # ─── Dashboard Page ───

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        index = STATIC_DIR / "index.html"
        return HTMLResponse(content=index.read_text(encoding="utf-8"))

    @app.get("/style.css")
    async def css():
        return FileResponse(STATIC_DIR / "style.css", media_type="text/css")

    @app.get("/app.js")
    async def js():
        return FileResponse(STATIC_DIR / "app.js", media_type="application/javascript")

    # ─── API Endpoints ───

    @app.get("/api/stats")
    async def get_stats():
        """Get ecosystem-wide statistics."""
        all_tools = await db.list_tools(status=ToolStatus.ACTIVE, limit=1000)
        total_uses = sum(t.total_uses for t in all_tools)
        total_agents = len(set(t.author_agent_id for t in all_tools))
        avg_fitness = sum(t.fitness_score for t in all_tools) / len(all_tools) if all_tools else 0

        return {
            "total_tools": len(all_tools),
            "total_uses": total_uses,
            "unique_agents": total_agents,
            "avg_fitness": round(avg_fitness, 4),
        }

    @app.get("/api/tools")
    async def list_tools(limit: int = 50, status: str = "active"):
        """List all tools with details."""
        tool_status = ToolStatus.ACTIVE if status == "active" else None
        tools = await db.list_tools(status=tool_status, limit=limit)

        return {
            "tools": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "fitness_score": t.fitness_score,
                    "trust_level": t.trust_level.value if hasattr(t.trust_level, 'value') else t.trust_level,
                    "status": t.status.value if hasattr(t.status, 'value') else t.status,
                    "total_uses": t.total_uses,
                    "successful_uses": t.successful_uses,
                    "unique_agents": t.unique_agents,
                    "tags": t.tags,
                    "version": t.version,
                    "parent_tool_id": t.parent_tool_id,
                    "author_agent_id": t.author_agent_id,
                    "avg_execution_time_ms": t.avg_execution_time_ms,
                    "content_hash": t.content_hash[:16] + "..." if t.content_hash else "",
                    "created_at": t.created_at.isoformat() if t.created_at else "",
                }
                for t in tools
            ],
            "total": len(tools),
        }

    @app.get("/api/tools/{tool_id}")
    async def get_tool(tool_id: str):
        """Get full tool details including code."""
        tool = await db.get_tool(tool_id)
        if not tool:
            raise HTTPException(status_code=404, detail="Tool not found")

        return {
            "id": tool.id,
            "name": tool.name,
            "description": tool.description,
            "code": tool.code,
            "test_case": tool.test_case,
            "input_schema": tool.input_schema,
            "fitness_score": tool.fitness_score,
            "trust_level": tool.trust_level.value if hasattr(tool.trust_level, 'value') else tool.trust_level,
            "status": tool.status.value if hasattr(tool.status, 'value') else tool.status,
            "total_uses": tool.total_uses,
            "successful_uses": tool.successful_uses,
            "unique_agents": tool.unique_agents,
            "tags": tool.tags,
            "version": tool.version,
            "parent_tool_id": tool.parent_tool_id,
            "content_hash": tool.content_hash,
            "author_agent_id": tool.author_agent_id,
            "created_at": tool.created_at.isoformat() if tool.created_at else "",
        }

    @app.get("/api/tools/{tool_id}/provenance")
    async def get_provenance(tool_id: str):
        """Get provenance chain for a tool."""
        chain = await db.get_provenance_chain(tool_id)
        return {
            "chain": [
                {
                    "tool_id": p.tool_id,
                    "version": p.version,
                    "content_hash": p.content_hash[:16] + "...",
                    "parent_hash": (p.parent_hash[:16] + "...") if p.parent_hash else None,
                    "security_scan": p.security_scan.value if hasattr(p.security_scan, 'value') else p.security_scan,
                    "execution_time_ms": p.performance.execution_time_ms if p.performance else 0,
                    "memory_peak_mb": p.performance.memory_peak_mb if p.performance else 0,
                    "signature": p.signature[:16] + "..." if p.signature else "",
                    "created_at": p.created_at.isoformat() if p.created_at else "",
                }
                for p in chain
            ],
        }

    @app.get("/api/activity")
    async def get_activity(limit: int = 20):
        """Get recent activity feed."""
        # Get recent tools as activity
        tools = await db.list_tools(limit=limit)
        activities = []
        for t in tools:
            activities.append({
                "type": "tool_published",
                "tool_name": t.name,
                "tool_id": t.id,
                "agent_id": t.author_agent_id,
                "fitness_score": t.fitness_score,
                "timestamp": t.created_at.isoformat() if t.created_at else "",
                "tags": t.tags,
            })

        return {"activities": sorted(activities, key=lambda a: a["timestamp"], reverse=True)}

    @app.get("/api/leaderboard")
    async def get_leaderboard(limit: int = 10):
        """Get top tools by fitness score."""
        tools = await db.list_tools(status=ToolStatus.ACTIVE, limit=limit)
        # Sort by fitness
        tools.sort(key=lambda t: t.fitness_score, reverse=True)

        return {
            "leaderboard": [
                {
                    "rank": i + 1,
                    "name": t.name,
                    "id": t.id,
                    "fitness_score": t.fitness_score,
                    "total_uses": t.total_uses,
                    "trust_level": t.trust_level.value if hasattr(t.trust_level, 'value') else t.trust_level,
                    "author": t.author_agent_id,
                }
                for i, t in enumerate(tools[:limit])
            ],
        }

    return app


# ─── CLI Entry Point ───

def main():
    """Run the dashboard server."""
    import uvicorn
    config = AgentEvolutionConfig()
    set_config(config)
    print("🖥️  AgentEvolution Dashboard", file=sys.stderr)
    print(f"   http://localhost:8080", file=sys.stderr)
    uvicorn.run(create_app(), host="0.0.0.0", port=8080, log_level="info")


if __name__ == "__main__":
    main()

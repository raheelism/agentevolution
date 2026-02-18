"""The Forge — Tool Publishing System.

Handles tool submission, forking, and updates. This is where agents
publish their solutions to become reusable tools for all agents.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from agentevolution.config import get_config
from agentevolution.forge.normalizer import normalize_code, extract_function_name, validate_code_size
from agentevolution.forge.schema_gen import generate_input_schema, extract_function_info
from agentevolution.storage.database import Database
from agentevolution.storage.vector_store import VectorStore
from agentevolution.storage.models import (
    Tool,
    ToolSubmission,
    ToolStatus,
    ForkRequest,
)
from agentevolution.utils.hashing import hash_tool


class Forge:
    """The Forge — where agents publish tools."""

    def __init__(self, db: Database, vector_store: VectorStore):
        self.db = db
        self.vector_store = vector_store
        self.config = get_config().forge

    async def submit_tool(self, submission: ToolSubmission) -> Tool:
        """Process a tool submission from an agent.

        Steps:
        1. Validate and normalize the code
        2. Extract function info and generate schema
        3. Create tool record with PENDING status
        4. Returns tool (Gauntlet verification happens next)
        """
        # Validate
        validate_code_size(submission.code, self.config.max_code_size_bytes)
        if len(submission.description) > self.config.max_description_length:
            raise ValueError(
                f"Description too long ({len(submission.description)} chars, "
                f"max {self.config.max_description_length})"
            )

        # Normalize code
        code = normalize_code(submission.code)
        test_case = normalize_code(submission.test_case)

        # Extract function info
        func_info = extract_function_info(code)
        name = func_info["name"] or extract_function_name(code)
        input_schema = generate_input_schema(code)

        # Generate content hash
        content_hash = hash_tool(code, submission.description, test_case)

        # Create tool
        tool = Tool(
            id=str(uuid.uuid4()),
            name=name,
            code=code,
            description=submission.description,
            test_case=test_case,
            dependencies=submission.dependencies,
            tags=submission.tags,
            input_schema=input_schema,
            output_type=func_info.get("return_type", "any"),
            status=ToolStatus.PENDING,
            content_hash=content_hash,
            author_agent_id=submission.author_agent_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Save to database
        await self.db.save_tool(tool)

        return tool

    async def fork_tool(self, request: ForkRequest) -> Tool:
        """Fork an existing tool to create an improved version.

        Creates a new tool with provenance linking back to the original.
        """
        # Get the parent tool
        parent = await self.db.get_tool(request.parent_tool_id)
        if parent is None:
            raise ValueError(f"Parent tool not found: {request.parent_tool_id}")

        # Normalize
        code = normalize_code(request.code)
        test_case = normalize_code(request.test_case)

        # Extract info
        func_info = extract_function_info(code)
        name = func_info["name"] or parent.name
        input_schema = generate_input_schema(code)
        content_hash = hash_tool(code, request.description, test_case)

        # Create forked tool
        tool = Tool(
            id=str(uuid.uuid4()),
            name=f"{name}",
            code=code,
            description=request.description,
            test_case=test_case,
            dependencies=parent.dependencies,
            tags=parent.tags,
            input_schema=input_schema,
            output_type=func_info.get("return_type", "any"),
            status=ToolStatus.PENDING,
            content_hash=content_hash,
            parent_tool_id=parent.id,
            version=parent.version + 1,
            author_agent_id=request.author_agent_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        await self.db.save_tool(tool)

        return tool

    async def activate_tool(self, tool: Tool) -> Tool:
        """Activate a tool after it passes The Gauntlet.

        Updates status and adds to the vector store for discovery.
        """
        tool.status = ToolStatus.ACTIVE
        await self.db.save_tool(tool)
        self.vector_store.add_tool(tool)
        return tool

    async def delist_tool(self, tool_id: str) -> None:
        """Delist a tool (remove from active registry)."""
        await self.db.update_tool_status(tool_id, ToolStatus.DELISTED)
        self.vector_store.remove_tool(tool_id)

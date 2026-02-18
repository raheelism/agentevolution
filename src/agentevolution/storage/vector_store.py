"""AgentEvolution Vector Store — ChromaDB for semantic tool embeddings."""

from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from agentevolution.storage.models import Tool, ToolSummary, DiscoveryResult, ToolStatus


class VectorStore:
    """ChromaDB-backed vector store for semantic tool discovery."""

    def __init__(self, data_dir: Path, collection_name: str = "agentevolution_tools"):
        self.data_dir = data_dir
        self.collection_name = collection_name
        self._client: chromadb.ClientAPI | None = None
        self._collection: chromadb.Collection | None = None

    def connect(self) -> None:
        """Initialize ChromaDB with persistent storage."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self.data_dir / "chromadb"),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            raise RuntimeError("VectorStore not connected. Call connect() first.")
        return self._collection

    def add_tool(self, tool: Tool) -> None:
        """Add or update a tool's embedding in the vector store."""
        # Build a rich document for embedding
        document = self._build_document(tool)

        self.collection.upsert(
            ids=[tool.id],
            documents=[document],
            metadatas=[{
                "name": tool.name,
                "description": tool.description[:500],
                "status": tool.status.value,
                "trust_level": tool.trust_level.value,
                "fitness_score": tool.fitness_score,
                "total_uses": tool.total_uses,
                "tags": ",".join(tool.tags),
                "author_agent_id": tool.author_agent_id,
            }],
        )

    def remove_tool(self, tool_id: str) -> None:
        """Remove a tool from the vector store."""
        try:
            self.collection.delete(ids=[tool_id])
        except Exception:
            pass  # Silently ignore if not found

    def search(
        self,
        query: str,
        max_results: int = 10,
        min_similarity: float = 0.3,
        status_filter: ToolStatus | None = ToolStatus.ACTIVE,
    ) -> list[DiscoveryResult]:
        """Semantic search for tools matching a natural language query."""
        where_filter = None
        if status_filter:
            where_filter = {"status": status_filter.value}

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=min(max_results, self.collection.count() or 1),
                where=where_filter if where_filter and self.collection.count() > 0 else None,
            )
        except Exception:
            return []

        if not results or not results["ids"] or not results["ids"][0]:
            return []

        discovery_results = []
        for i, tool_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 1.0

            # ChromaDB returns distance, convert to similarity (cosine)
            similarity = 1.0 - distance

            if similarity < min_similarity:
                continue

            summary = ToolSummary(
                id=tool_id,
                name=metadata.get("name", ""),
                description=metadata.get("description", ""),
                fitness_score=metadata.get("fitness_score", 0.0),
                trust_level=metadata.get("trust_level", 0),
                status=ToolStatus(metadata.get("status", "active")),
                total_uses=metadata.get("total_uses", 0),
                tags=metadata.get("tags", "").split(",") if metadata.get("tags") else [],
            )

            discovery_results.append(DiscoveryResult(
                tool=summary,
                similarity_score=round(similarity, 4),
                reason=f"Semantic match (similarity: {similarity:.2%})",
            ))

        # Sort by combined score: similarity * fitness_weight
        discovery_results.sort(
            key=lambda r: r.similarity_score * (0.7 + 0.3 * r.tool.fitness_score),
            reverse=True,
        )

        return discovery_results

    def _build_document(self, tool: Tool) -> str:
        """Build a rich document string for embedding."""
        parts = [
            f"Tool: {tool.name}",
            f"Description: {tool.description}",
        ]
        if tool.tags:
            parts.append(f"Tags: {', '.join(tool.tags)}")
        if tool.input_schema:
            params = tool.input_schema.get("properties", {})
            if params:
                param_str = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in params.items())
                parts.append(f"Parameters: {param_str}")
        return "\n".join(parts)

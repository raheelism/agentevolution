"""Tool Recipes — Compositional tool chains.

Pre-verified pipelines of tools that solve complex multi-step tasks.
"""

from __future__ import annotations

from agentevolution.storage.database import Database
from agentevolution.storage.models import Recipe, RecipeStep, ToolSummary


class RecipeEngine:
    """Manages compositional tool chains (recipes)."""

    def __init__(self, db: Database):
        self.db = db

    async def create_recipe(
        self,
        name: str,
        description: str,
        tool_ids: list[str],
        author_agent_id: str = "anonymous",
    ) -> Recipe:
        """Create a new recipe from a sequence of tools.

        Validates that all tools exist and calculates aggregate fitness.
        """
        steps: list[RecipeStep] = []
        total_fitness = 0.0

        for i, tool_id in enumerate(tool_ids):
            tool = await self.db.get_tool(tool_id)
            if tool is None:
                raise ValueError(f"Tool not found: {tool_id}")

            steps.append(RecipeStep(
                tool_id=tool.id,
                tool_name=tool.name,
                description=tool.description,
                order=i,
            ))
            total_fitness += tool.fitness_score

        # Average fitness across chain
        avg_fitness = total_fitness / len(steps) if steps else 0.0

        recipe = Recipe(
            name=name,
            description=description,
            steps=steps,
            total_fitness=round(avg_fitness, 4),
            author_agent_id=author_agent_id,
        )

        await self.db.save_recipe(recipe)
        return recipe

    async def list_recipes(self, limit: int = 20) -> list[Recipe]:
        """List all recipes ordered by fitness."""
        return await self.db.list_recipes(limit=limit)

    async def get_recipe_tools(self, recipe: Recipe) -> list[ToolSummary]:
        """Get tool summaries for each step in a recipe."""
        summaries: list[ToolSummary] = []
        for step in sorted(recipe.steps, key=lambda s: s.order):
            tool = await self.db.get_tool(step.tool_id)
            if tool:
                summaries.append(ToolSummary(
                    id=tool.id, name=tool.name, description=tool.description,
                    fitness_score=tool.fitness_score, trust_level=tool.trust_level,
                    status=tool.status, total_uses=tool.total_uses, tags=tool.tags,
                ))
        return summaries

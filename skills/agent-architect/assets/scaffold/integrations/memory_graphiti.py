"""Temporal knowledge-graph memory via Graphiti (repo: getzep/graphiti, install: graphiti-core[anthropic]).

Needs a graph DB: Neo4j, or FalkorDB:
    docker run -p 6379:6379 -p 3000:3000 -it --rm falkordb/falkordb:latest

Choose Graphiti only when memory is relationship-centric and changes over time
(who reports to whom, what was true when). For simple user facts use mem0.

This file is a starting point: wire the client using the repo's current examples
(`$AGENT_ARCHITECT_REPOS/getzep_graphiti/examples/`); the API evolves quickly.
"""
from __future__ import annotations

from agent.core import wrap_untrusted


async def recall(query: str) -> str:
    raise NotImplementedError(
        "Wire Graphiti here: see getzep_graphiti/examples/quickstart in the reference repos. "
        "Return wrap_untrusted('graph_memory', facts)."
    )


__all__ = ["recall", "wrap_untrusted"]

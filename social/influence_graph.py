
# ── social/influence_graph.py ─────────────────────────────────────────────────
"""
Thin wrapper around a NetworkX DiGraph.
Kept in its own file so the simulation environment can import it independently.
"""
# social/influence_graph.py

import networkx as nx


class InfluenceGraph:
    def __init__(self):
        self._g = nx.DiGraph()

    def add_persona(self, pid: str, archetype: str):
        self._g.add_node(pid, archetype=archetype)

    def add_edge(self, src: str, tgt: str, weight: float = 1.0):
        """src influences tgt."""
        self._g.add_edge(src, tgt, weight=weight)

    def get_influenced_by(self, pid: str) -> list[str]:
        """Return list of persona IDs that pid directly influences."""
        return list(self._g.successors(pid))

    def get_influencers_of(self, pid: str) -> list[str]:
        """Return list of persona IDs that directly influence pid."""
        return list(self._g.predecessors(pid))

    def all_edges(self) -> list[tuple[str, str]]:
        return list(self._g.edges())

    def to_dict(self) -> dict:
        return nx.node_link_data(self._g)


# ── Quick local test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    from models.state import SimulationState

    parsed = {
        "entities":          ["free tier", "14-day trial"],
        "stakes":            ["user trust", "MRR", "churn rate"],
        "ambiguities":       ["no grace period for existing users"],
        "affected_segments": ["power_user", "casual_user", "enterprise_buyer",
                              "churned_user", "internal_skeptic", "competitor_analyst"],
        "constraints":       ["automatic migration"],
    }

    state  = SimulationState(parsed_scenario=parsed)
    result = persona_factory_node(state)

    if result.error:
        print(f"❌ {result.error}")
    else:
        print(f"✅ Spawned {len(result.personas)} personas:\n")
        for p in result.personas:
            print(f"  [{p.archetype}] {p.name} — {p.emotional_baseline}")
            print(f"    incentives: {p.incentives}")
            print(f"    influences: {p.social_connections}\n")
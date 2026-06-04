
# ═══════════════════════════════════════════════════════════════════════════════
# graph/orchestrator.py
# ═══════════════════════════════════════════════════════════════════════════════
"""
LangGraph state machine wiring all 5 agents into a single pipeline.

Flow:
  scenario_parser
      ↓
  persona_factory          ←─────────────────────────┐
      ↓                                               │  (re-run loop)
  simulation_env                                      │
      ↓                                               │
  emergent_tracker                                    │
      ↓                                               │
  confidence_checker ──(score < threshold)────────────┘
      ↓
  (score >= threshold OR max reruns hit)
      ↓
  outcome_report
      ↓
  END
"""

from __future__ import annotations
import uuid

from langgraph.graph import StateGraph, END

from agents.scenario_parser   import scenario_parser_node
from agents.persona_factory   import persona_factory_node
from agents.simulation_env    import simulation_env_node
from agents.emergent_tracker  import emergent_tracker_node
from agents.confidence_checker import confidence_checker_node, should_rerun
from agents.outcome_report    import outcome_report_node
from models.state             import SimulationState


# ── Adapter: LangGraph passes dict, our nodes expect SimulationState ──────────

def _wrap(fn):
    """Convert a SimulationState node into a dict-in / dict-out LangGraph node."""
    def wrapped(state: dict) -> dict:
        sim_state = SimulationState(**state)
        result    = fn(sim_state)
        return result.model_dump()
    return wrapped


def _should_rerun_dict(state: dict) -> str:
    return should_rerun(SimulationState(**state))


# ── Build graph ───────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(dict)

    g.add_node("scenario_parser",    _wrap(scenario_parser_node))
    g.add_node("persona_factory",    _wrap(persona_factory_node))
    g.add_node("simulation_env",     _wrap(simulation_env_node))
    g.add_node("emergent_tracker",   _wrap(emergent_tracker_node))
    g.add_node("confidence_checker", _wrap(confidence_checker_node))
    g.add_node("outcome_report",     _wrap(outcome_report_node))

    g.set_entry_point("scenario_parser")

    g.add_edge("scenario_parser",  "persona_factory")
    g.add_edge("persona_factory",  "simulation_env")
    g.add_edge("simulation_env",   "emergent_tracker")
    g.add_edge("emergent_tracker", "confidence_checker")

    # conditional: re-run loop or proceed to report
    g.add_conditional_edges(
        "confidence_checker",
        _should_rerun_dict,
        {
            "persona_factory": "persona_factory",
            "outcome_report":  "outcome_report",
        },
    )

    g.add_edge("outcome_report", END)
    return g


# Compiled graph (singleton — import this in api/main.py)
compiled_graph = build_graph().compile()


# ── Convenience runner ────────────────────────────────────────────────────────

def run_simulation(raw_scenario: str, sim_id: str | None = None) -> dict:
    """
    Run the full pipeline synchronously.
    Returns the final SimulationState as a dict.
    """
    init_state = SimulationState(
        raw_scenario  = raw_scenario,
        simulation_id = sim_id or uuid.uuid4().hex,
    ).model_dump()

    final = compiled_graph.invoke(init_state)
    return final

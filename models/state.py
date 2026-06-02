from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field
from langgraph.graph import add_messages
from typing import Annotated


class PersonaProfile(BaseModel):
    id: str
    name: str
    archetype: str                  # e.g. "power_user", "enterprise_buyer"
    incentives: list[str]
    emotional_baseline: str         # e.g. "skeptical", "enthusiastic"
    memory_seed: str                # priming context for Zep session
    social_connections: list[str]   # other persona IDs this agent influences


class PersonaReaction(BaseModel):
    persona_id: str
    emotional_response: str
    rational_response: str
    chosen_action: str              # "churn" | "upgrade" | "post_negative" | "post_positive" | "wait"
    influence_targets: list[str]    # persona IDs this reaction nudges
    raw_output: str                 # full LLM output for audit


class EmergentEvent(BaseModel):
    name: str                       # e.g. "negative_viral_loop"
    description: str
    causal_chain: list[str]         # ordered list of persona IDs / events in chain
    severity: str                   # "low" | "medium" | "high"


class OutcomeReport(BaseModel):
    churn_pct_range: tuple[float, float]
    revenue_impact_range: tuple[float, float]   # USD, negative = loss
    pr_risk_score: float                         # 0.0 – 1.0
    unexpected_effects: list[str]
    recommendations: list[str]
    citations: dict[str, str]       # claim → persona_id that produced it
    confidence_score: float         # 0.0 – 1.0


class SimulationState(BaseModel):
    # ── inputs ────────────────────────────────────────────
    raw_scenario: str = ""

    # ── parser output ─────────────────────────────────────
    parsed_scenario: dict[str, Any] = Field(default_factory=dict)
    # shape: { entities, stakes, ambiguities, affected_segments, constraints }

    # ── persona factory output ────────────────────────────
    personas: list[PersonaProfile] = Field(default_factory=list)

    # ── simulation output ─────────────────────────────────
    reactions: list[PersonaReaction] = Field(default_factory=list)
    interaction_log: list[str] = Field(default_factory=list)

    # ── emergent tracker output ───────────────────────────
    emergent_events: list[EmergentEvent] = Field(default_factory=list)

    # ── confidence checker ────────────────────────────────
    confidence_score: float = 0.0
    rerun_count: int = 0
    max_reruns: int = 2
    assumption_branches: list[str] = Field(default_factory=list)

    # ── final report ──────────────────────────────────────
    outcome_report: OutcomeReport | None = None

    # ── metadata ──────────────────────────────────────────
    simulation_id: str = ""
    error: str = ""
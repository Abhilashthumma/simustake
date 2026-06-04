# ── agents/confidence_checker.py ──────────────────────────────────────────────
"""
ConfidenceCheckerAgent — LangGraph node (Step 6)

Input : SimulationState (full — reactions, emergent_events, personas, parsed_scenario)
Output: SimulationState.confidence_score     (float 0.0–1.0)
        SimulationState.assumption_branches  (list[str], populated if re-run needed)
        SimulationState.rerun_count          (incremented on re-run)

LangGraph routing:
  confidence >= THRESHOLD  → proceed to outcome_report_node
  confidence <  THRESHOLD
    AND rerun_count < max_reruns → loop back to persona_factory_node
                                   with new assumption_branches injected
    AND rerun_count >= max_reruns → proceed anyway (best effort)

Confidence is scored on five dimensions (each 0–1, weighted):
  1. persona_coverage   — did we get reactions from all personas?          (0.25)
  2. action_diversity   — are actions varied, not all the same?            (0.20)
  3. influence_activity — did social graph actually propagate anything?    (0.20)
  4. emergent_richness  — did the tracker surface meaningful events?       (0.20)
  5. ambiguity_coverage — did reactions address scenario ambiguities?      (0.15)
                          (LLM-scored sub-dimension)
"""

from __future__ import annotations
import json
import os
import re
from collections import Counter

from dotenv import load_dotenv
from groq import Groq

from models.state import SimulationState

load_dotenv()

_client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL   = "llama-3.3-70b-versatile"

CONFIDENCE_THRESHOLD = 0.65   # below this → re-run


# ── Dimension scorers ─────────────────────────────────────────────────────────

def _score_persona_coverage(state: SimulationState) -> float:
    """Fraction of personas that produced a valid reaction."""
    if not state.personas:
        return 0.0
    persona_ids   = {p.id for p in state.personas}
    reacted_ids   = {r.persona_id for r in state.reactions if r.chosen_action != "wait" or r.emotional_response}
    return len(reacted_ids & persona_ids) / len(persona_ids)


def _score_action_diversity(state: SimulationState) -> float:
    """
    Shannon-inspired diversity: penalise simulations where everyone does the same thing.
    Score = unique_actions / total_possible_actions (5)
    """
    if not state.reactions:
        return 0.0
    unique = len({r.chosen_action for r in state.reactions})
    return min(unique / 3, 1.0)   # 3+ unique actions = full score


def _score_influence_activity(state: SimulationState) -> float:
    """Did influence propagation actually happen? (Round 2 log entries are the signal)"""
    if not state.interaction_log:
        return 0.0
    round2_entries = [l for l in state.interaction_log if "[Round 2]" in l]
    if not round2_entries:
        return 0.3   # partial — graph existed but nothing propagated
    # reward more propagation up to a cap
    return min(len(round2_entries) / max(len(state.personas) * 0.5, 1), 1.0)


def _score_emergent_richness(state: SimulationState) -> float:
    """More events + higher severity = richer simulation."""
    if not state.emergent_events:
        return 0.0
    severity_weights = {"low": 0.3, "medium": 0.6, "high": 1.0}
    raw = sum(severity_weights.get(e.severity, 0.3) for e in state.emergent_events)
    return min(raw / 3.0, 1.0)   # 3 high-severity events = full score


def _score_ambiguity_coverage(state: SimulationState) -> float:
    """
    LLM sub-scorer: did persona reactions surface or address the scenario ambiguities?
    Returns 0.0 on any failure (best-effort).
    """
    ambiguities = state.parsed_scenario.get("ambiguities", [])
    if not ambiguities:
        return 0.8   # no ambiguities = not penalised

    reaction_texts = " ".join(
        f"{r.emotional_response} {r.rational_response}"
        for r in state.reactions
    )

    prompt = (
        f"Scenario ambiguities: {json.dumps(ambiguities)}\n\n"
        f"Persona reaction text (combined):\n{reaction_texts[:2000]}\n\n"
        "Score 0.0–1.0: how well do the reactions surface or address these ambiguities?\n"
        "Return ONLY a JSON object: {\"score\": <float>}"
    )

    try:
        resp = _client.chat.completions.create(
            model=MODEL,
            temperature=0.0,
            max_tokens=64,
            messages=[
                {"role": "system", "content": "You are a simulation quality evaluator. Return only JSON."},
                {"role": "user",   "content": prompt},
            ],
        )
        raw  = resp.choices[0].message.content.strip()
        raw  = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        data = json.loads(raw)
        return float(max(0.0, min(1.0, data.get("score", 0.5))))
    except Exception:
        return 0.5   # neutral fallback


def _compute_confidence(state: SimulationState) -> tuple[float, dict[str, float]]:
    dims = {
        "persona_coverage":   (_score_persona_coverage(state),   0.25),
        "action_diversity":   (_score_action_diversity(state),    0.20),
        "influence_activity": (_score_influence_activity(state),  0.20),
        "emergent_richness":  (_score_emergent_richness(state),   0.20),
        "ambiguity_coverage": (_score_ambiguity_coverage(state),  0.15),
    }
    total  = sum(score * weight for score, weight in dims.values())
    scores = {k: round(v[0], 3) for k, v in dims.items()}
    return round(total, 3), scores


# ── Assumption branch generator ───────────────────────────────────────────────

BRANCH_PROMPT = """
A stakeholder simulation scored low on confidence.
Given the scenario and the weak dimension scores, generate 2-3 alternative
assumption branches that could produce a richer, more diverse simulation.

Each branch is a short instruction string that will be injected into the
Persona Factory to nudge it toward different behaviors.

Return ONLY a JSON array of strings — no markdown, no commentary.
Example: ["Assume 30% of users are price-sensitive and will churn immediately",
          "Include a vocal advocate persona who defends the decision publicly"]
""".strip()


def _generate_assumption_branches(state: SimulationState, dim_scores: dict) -> list[str]:
    weak_dims = [d for d, s in dim_scores.items() if s < 0.5]
    prompt = (
        f"Scenario: {json.dumps(state.parsed_scenario)}\n\n"
        f"Weak confidence dimensions: {weak_dims}\n"
        f"Dimension scores: {json.dumps(dim_scores)}\n"
        f"Re-run #{state.rerun_count + 1} of {state.max_reruns}"
    )
    try:
        resp = _client.chat.completions.create(
            model=MODEL,
            temperature=0.7,
            max_tokens=512,
            messages=[
                {"role": "system", "content": BRANCH_PROMPT},
                {"role": "user",   "content": prompt},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        branches = json.loads(raw)
        return [b for b in branches if isinstance(b, str)]
    except Exception:
        return ["Introduce more diverse emotional baselines across personas",
                "Add a persona who publicly defends the decision"]


# ── LangGraph node ─────────────────────────────────────────────────────────────
def confidence_checker_node(state: SimulationState) -> SimulationState:
    if state.error:
        return state

    confidence, dim_scores = _compute_confidence(state)

    print(f"\n📊 Confidence score: {confidence:.3f} (threshold: {CONFIDENCE_THRESHOLD})")
    for dim, score in dim_scores.items():
        bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
        print(f"   {dim:<22} {bar}  {score:.2f}")

    updated = state.model_copy(update={
        "confidence_score": confidence,
        "error": "",
    })

    if confidence < CONFIDENCE_THRESHOLD and state.rerun_count < state.max_reruns:
        branches = _generate_assumption_branches(state, dim_scores)
        print(f"\n🔁 Re-running (attempt {state.rerun_count + 1}/{state.max_reruns})")
        print(f"   Branches: {branches}")
        updated = updated.model_copy(update={
            "assumption_branches": branches,
            "rerun_count":         state.rerun_count + 1,
            # clear stale simulation data so the re-run starts fresh
            "reactions":           [],
            "interaction_log":     [],
            "emergent_events":     [],
            "personas":            [],
        })

    return updated


# ── LangGraph routing function (used in graph/orchestrator.py, Step 8) ─────────
def should_rerun(state: SimulationState) -> str:
    """
    LangGraph conditional edge function.
    Returns the name of the next node to route to.
    """
    if (
        state.confidence_score < CONFIDENCE_THRESHOLD
        and state.rerun_count <= state.max_reruns
        and not state.personas   # cleared by confidence_checker_node on re-run
    ):
        return "persona_factory"
    return "outcome_report"


# ── Quick local test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    from models.state import (EmergentEvent, PersonaProfile,
                               PersonaReaction, SimulationState)

    personas = [
        PersonaProfile(id="power_user_01",     name="Ethan",  archetype="power_user",
                       incentives=[], emotional_baseline="ambitious",
                       memory_seed="", social_connections=["casual_user_02"]),
        PersonaProfile(id="casual_user_02",    name="Lily",   archetype="casual_user",
                       incentives=[], emotional_baseline="relaxed",
                       memory_seed="", social_connections=[]),
        PersonaProfile(id="enterprise_buyer_03", name="Ryan", archetype="enterprise_buyer",
                       incentives=[], emotional_baseline="pragmatic",
                       memory_seed="", social_connections=[]),
    ]

    reactions = [
        PersonaReaction(persona_id="power_user_01",     chosen_action="churn",
                        emotional_response="Outraged at removal of free tier.",
                        rational_response="Will migrate to competitor.",
                        influence_targets=["casual_user_02"], raw_output=""),
        PersonaReaction(persona_id="casual_user_02",    chosen_action="churn",
                        emotional_response="Influenced by power user's outrage.",
                        rational_response="Not worth paying for basic features.",
                        influence_targets=[], raw_output=""),
        PersonaReaction(persona_id="enterprise_buyer_03", chosen_action="wait",
                        emotional_response="Monitoring the situation carefully.",
                        rational_response="Need to see churn data before committing.",
                        influence_targets=[], raw_output=""),
    ]

    emergent = [
        EmergentEvent(name="negative_viral_loop",
                      description="Churn cascading via social graph.",
                      causal_chain=["power_user_01", "casual_user_02"],
                      severity="high"),
        EmergentEvent(name="enterprise_freeze",
                      description="Enterprise deal stalled.",
                      causal_chain=["enterprise_buyer_03"],
                      severity="high"),
    ]

    logs = [
        "[Round 1] Ethan → churn",
        "[Round 2] Lily → churn (influenced by Ethan)",
    ]

    parsed = {
        "entities":          ["free tier", "14-day trial"],
        "stakes":            ["MRR", "user trust"],
        "ambiguities":       ["no grace period mentioned"],
        "affected_segments": ["power_user", "casual_user", "enterprise_buyer"],
        "constraints":       ["automatic migration"],
    }

    state = SimulationState(
        personas=personas, reactions=reactions,
        emergent_events=emergent, interaction_log=logs,
        parsed_scenario=parsed,
    )

    result = confidence_checker_node(state)
    print(f"\n✅ Final confidence: {result.confidence_score}")
    print(f"   Re-run triggered: {result.rerun_count > 0}")
    if result.assumption_branches:
        print(f"   Branches: {result.assumption_branches}")
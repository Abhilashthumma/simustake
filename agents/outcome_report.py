# ── agents/outcome_report.py ──────────────────────────────────────────────────
"""
OutcomeReportAgent — LangGraph node (Step 7)

Input : SimulationState (full — reactions, emergent_events, personas,
                         parsed_scenario, confidence_score)
Output: SimulationState.outcome_report  (OutcomeReport)

Two-pass generation:
  Pass 1 — deterministic metrics
            churn %, revenue impact range, PR risk score
            computed directly from reaction + emergent data (no LLM)
  Pass 2 — LLM synthesis
            unexpected effects, recommendations
            each claim cited back to the persona_id that produced it
"""

from __future__ import annotations
import json
import os
import re
from collections import Counter

from dotenv import load_dotenv
from groq import Groq

from models.state import OutcomeReport, SimulationState

load_dotenv()

_client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL   = "llama-3.3-70b-versatile"


# ── Pass 1: deterministic metrics ────────────────────────────────────────────

def _churn_pct_range(state: SimulationState) -> tuple[float, float]:
    """
    Base churn % from reactions, widened by emergent severity.
    Returns (low_pct, high_pct) as 0–100 floats.
    """
    if not state.reactions:
        return (0.0, 0.0)

    total   = len(state.reactions)
    churned = sum(1 for r in state.reactions if r.chosen_action == "churn")
    base    = churned / total * 100

    # emergent multiplier — high-severity viral loops widen the range upward
    high_events = sum(1 for e in state.emergent_events if e.severity == "high")
    med_events  = sum(1 for e in state.emergent_events if e.severity == "medium")
    multiplier  = 1.0 + (high_events * 0.25) + (med_events * 0.10)

    low  = round(base, 1)
    high = round(min(base * multiplier, 100.0), 1)
    return (low, high)


def _revenue_impact_range(
    state: SimulationState,
    avg_revenue_per_user: float = 50.0,   # USD/month default assumption
) -> tuple[float, float]:
    """
    Negative = revenue loss. Positive = gain from upgrades.
    Persona count is used as a proxy for user-base sample size.
    """
    if not state.reactions:
        return (0.0, 0.0)

    action_counts = Counter(r.chosen_action for r in state.reactions)
    n             = len(state.reactions)

    churn_frac   = action_counts.get("churn",   0) / n
    upgrade_frac = action_counts.get("upgrade", 0) / n

    # scale factor: treat each persona as representing 100 real users
    scale = 100 * avg_revenue_per_user

    net_low  = round((upgrade_frac - churn_frac) * scale, 2)
    # high estimate: emergent viral churn could double actual churn
    high_events = sum(1 for e in state.emergent_events if e.severity == "high")
    churn_high  = min(churn_frac * (1 + high_events * 0.3), 1.0)
    net_high    = round((upgrade_frac - churn_high) * scale, 2)

    low  = min(net_low, net_high)
    high = max(net_low, net_high)
    return (low, high)


def _pr_risk_score(state: SimulationState) -> float:
    """
    0.0 (no risk) → 1.0 (crisis).
    Driven by post_negative actions + high-severity emergent events.
    """
    if not state.reactions:
        return 0.0

    neg_posts   = sum(1 for r in state.reactions if r.chosen_action == "post_negative")
    pos_posts   = sum(1 for r in state.reactions if r.chosen_action == "post_positive")
    high_events = sum(1 for e in state.emergent_events if e.severity == "high")
    pr_firestorm= any(e.name == "pr_firestorm" for e in state.emergent_events)

    score = (neg_posts * 0.15) + (high_events * 0.20) - (pos_posts * 0.10)
    if pr_firestorm:
        score += 0.30

    return round(max(0.0, min(score, 1.0)), 3)


# ── Pass 2: LLM synthesis ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are a senior product strategist writing a final simulation report.
You have access to stakeholder reactions, emergent events, and computed metrics.

Your job:
1. Identify 2-4 unexpected effects — things that weren't obvious from the
   scenario alone but emerged from the simulation.
2. Write 3-5 concrete, actionable recommendations to improve the outcome.
3. For EVERY claim, cite the persona_id or emergent event name that produced it.

Return ONLY valid JSON — no markdown fences, no commentary.

Schema:
{
  "unexpected_effects": [<string>, ...],
  "recommendations":    [<string>, ...],
  "citations":          {
      "<claim snippet (first 6 words)>": "<persona_id or emergent_event_name>"
  }
}

Rules:
- Citations must reference real persona_ids or event names from the input.
- Recommendations must be specific — avoid generic advice like "communicate better".
- unexpected_effects must reference concrete simulation outcomes, not hypotheticals.
""".strip()


def _build_llm_prompt(state: SimulationState, metrics: dict) -> str:
    reaction_summary = [
        {
            "persona_id": r.persona_id,
            "archetype":  next((p.archetype for p in state.personas if p.id == r.persona_id), ""),
            "action":     r.chosen_action,
            "emotion":    r.emotional_response[:150],
            "rational":   r.rational_response[:150],
        }
        for r in state.reactions
    ]

    emergent_summary = [
        {"name": e.name, "severity": e.severity, "description": e.description,
         "causal_chain": e.causal_chain}
        for e in state.emergent_events
    ]

    return (
        f"SCENARIO:\n{json.dumps(state.parsed_scenario, indent=2)}\n\n"
        f"COMPUTED METRICS:\n{json.dumps(metrics, indent=2)}\n\n"
        f"PERSONA REACTIONS:\n{json.dumps(reaction_summary, indent=2)}\n\n"
        f"EMERGENT EVENTS:\n{json.dumps(emergent_summary, indent=2)}\n\n"
        f"CONFIDENCE SCORE: {state.confidence_score}"
    )


def _llm_synthesis(state: SimulationState, metrics: dict) -> dict:
    prompt = _build_llm_prompt(state, metrics)
    try:
        resp = _client.chat.completions.create(
            model=MODEL,
            temperature=0.4,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        return json.loads(raw)
    except Exception as e:
        return {
            "unexpected_effects": [f"LLM synthesis failed: {e}"],
            "recommendations":    ["Review simulation logs manually."],
            "citations":          {},
        }


# ── LangGraph node ─────────────────────────────────────────────────────────────
def outcome_report_node(state: SimulationState) -> SimulationState:
    if state.error:
        return state
    if not state.reactions:
        return state.model_copy(update={"error": "outcome_report: no reactions to aggregate"})

    # Pass 1 — deterministic metrics
    churn_range   = _churn_pct_range(state)
    revenue_range = _revenue_impact_range(state)
    pr_risk       = _pr_risk_score(state)

    metrics = {
        "churn_pct_range":        churn_range,
        "revenue_impact_range":   revenue_range,
        "pr_risk_score":          pr_risk,
    }

    # Pass 2 — LLM synthesis
    synthesis = _llm_synthesis(state, metrics)

    report = OutcomeReport(
        churn_pct_range       = churn_range,
        revenue_impact_range  = revenue_range,
        pr_risk_score         = pr_risk,
        unexpected_effects    = synthesis.get("unexpected_effects", []),
        recommendations       = synthesis.get("recommendations", []),
        citations             = synthesis.get("citations", {}),
        confidence_score      = state.confidence_score,
    )

    return state.model_copy(update={"outcome_report": report, "error": ""})


# ── Pretty printer (reused by FastAPI in Step 8) ──────────────────────────────
def format_report(report: OutcomeReport) -> str:
    sep = "─" * 60
    lines = [
        sep,
        "📋  SIMUSTAKE OUTCOME REPORT",
        sep,
        f"  Churn range       : {report.churn_pct_range[0]}% – {report.churn_pct_range[1]}%",
        f"  Revenue impact    : ${report.revenue_impact_range[0]:,.0f} – ${report.revenue_impact_range[1]:,.0f} /mo",
        f"  PR risk score     : {report.pr_risk_score:.2f} / 1.00",
        f"  Confidence        : {report.confidence_score:.2f} / 1.00",
        "",
        "  ⚡ Unexpected effects:",
        *[f"    • {e}" for e in report.unexpected_effects],
        "",
        "  ✅ Recommendations:",
        *[f"    {i+1}. {r}" for i, r in enumerate(report.recommendations)],
        "",
        "  🔖 Citations:",
        *[f"    '{k}' ← {v}" for k, v in report.citations.items()],
        sep,
    ]
    return "\n".join(lines)


# ── Quick local test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    from models.state import (EmergentEvent, PersonaProfile,
                               PersonaReaction, SimulationState)

    personas = [
        PersonaProfile(id="power_user_01",      name="Ethan Thompson",
                       archetype="power_user",   incentives=[],
                       emotional_baseline="ambitious", memory_seed="",
                       social_connections=["casual_user_02"]),
        PersonaProfile(id="casual_user_02",     name="Lily Patel",
                       archetype="casual_user",  incentives=[],
                       emotional_baseline="relaxed", memory_seed="",
                       social_connections=[]),
        PersonaProfile(id="enterprise_buyer_03",name="Ryan Jenkins",
                       archetype="enterprise_buyer", incentives=[],
                       emotional_baseline="pragmatic", memory_seed="",
                       social_connections=[]),
        PersonaProfile(id="churned_user_04",    name="Sophia Rodriguez",
                       archetype="churned_user", incentives=[],
                       emotional_baseline="frustrated", memory_seed="",
                       social_connections=[]),
    ]

    reactions = [
        PersonaReaction(persona_id="power_user_01",      chosen_action="churn",
                        emotional_response="Two years of loyalty — now they want money.",
                        rational_response="Moving to competitor's free plan.",
                        influence_targets=["casual_user_02"], raw_output=""),
        PersonaReaction(persona_id="casual_user_02",     chosen_action="churn",
                        emotional_response="If power users are leaving, why should I stay?",
                        rational_response="14 days isn't enough to evaluate properly.",
                        influence_targets=[], raw_output=""),
        PersonaReaction(persona_id="enterprise_buyer_03",chosen_action="wait",
                        emotional_response="Watching before committing a 200-seat deal.",
                        rational_response="Churn signals instability — pausing evaluation.",
                        influence_targets=[], raw_output=""),
        PersonaReaction(persona_id="churned_user_04",    chosen_action="post_negative",
                        emotional_response="Called it. They never cared about free users.",
                        rational_response="Posting my experience to warn others.",
                        influence_targets=[], raw_output=""),
    ]

    emergent = [
        EmergentEvent(name="negative_viral_loop",
                      description="Churn cascading via social graph.",
                      causal_chain=["power_user_01", "casual_user_02"], severity="high"),
        EmergentEvent(name="enterprise_freeze",
                      description="200-seat deal stalled after user churn signals.",
                      causal_chain=["enterprise_buyer_03"], severity="high"),
        EmergentEvent(name="pr_firestorm",
                      description="Negative post from churned user amplifying churn signal.",
                      causal_chain=["churned_user_04"], severity="medium"),
    ]

    parsed = {
        "entities":          ["free tier", "14-day trial"],
        "stakes":            ["MRR", "user trust", "enterprise pipeline"],
        "ambiguities":       ["no grace period mentioned", "no grandfathering for power users"],
        "affected_segments": ["power_user", "casual_user", "enterprise_buyer", "churned_user"],
        "constraints":       ["automatic migration"],
    }

    state = SimulationState(
        personas=personas, reactions=reactions,
        emergent_events=emergent, parsed_scenario=parsed,
        interaction_log=["[Round 1] Ethan → churn",
                         "[Round 2] Lily → churn (influenced by Ethan)"],
        confidence_score=0.74,
    )

    result = outcome_report_node(state)

    if result.error:
        print(f"❌ {result.error}")
    else:
        print(format_report(result.outcome_report))
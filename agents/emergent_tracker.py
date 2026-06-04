# ── agents/emergent_tracker.py ────────────────────────────────────────────────
"""
EmergentBehaviorTracker — LangGraph node (Step 5)

Input : SimulationState.reactions + SimulationState.interaction_log
        + SimulationState.personas
Output: SimulationState.emergent_events  (list[EmergentEvent])

Two-pass detection:
  Pass 1 — deterministic rules scan reaction data for known patterns
            (fast, no LLM call, always runs)
  Pass 2 — LLM analyzes interaction log for novel / unexpected patterns
            (runs only if Pass 1 finds < 2 events OR interaction_log is rich)

Named patterns detected:
  - negative_viral_loop     : churn cascades through social graph
  - positive_viral_loop     : upgrade cascades through social graph
  - pr_firestorm            : 2+ post_negative actions from connected personas
  - silent_majority         : majority wait, masking underlying churn risk
  - competitor_opportunity  : churned + competitor personas both active
  - enterprise_freeze       : enterprise buyer waits after seeing user churn
"""

from __future__ import annotations
import json
import os
import re
from collections import Counter

from dotenv import load_dotenv
from groq import Groq

from models.state import EmergentEvent, PersonaReaction, PersonaProfile, SimulationState

load_dotenv()

_client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL   = "llama-3.3-70b-versatile"


# ── Pass 1: deterministic pattern detection ───────────────────────────────────

def _action_map(reactions: list[PersonaReaction]) -> dict[str, str]:
    return {r.persona_id: r.chosen_action for r in reactions}

def _archetype_map(personas: list[PersonaProfile]) -> dict[str, str]:
    return {p.id: p.archetype for p in personas}

def _connections_map(personas: list[PersonaProfile]) -> dict[str, list[str]]:
    return {p.id: p.social_connections for p in personas}


def _detect_viral_loop(
    actions: dict[str, str],
    connections: dict[str, list[str]],
    target_action: str,
    event_name: str,
    description: str,
) -> EmergentEvent | None:
    """Generic cascade detector: src takes action → at least one target also takes it."""
    chains = []
    for src, action in actions.items():
        if action != target_action:
            continue
        for tgt in connections.get(src, []):
            if actions.get(tgt) == target_action:
                chains.append(f"{src} → {tgt}")

    if chains:
        return EmergentEvent(
            name        = event_name,
            description = description,
            causal_chain= chains,
            severity    = "high" if len(chains) >= 2 else "medium",
        )
    return None


def _detect_pr_firestorm(
    reactions: list[PersonaReaction],
    connections: dict[str, list[str]],
) -> EmergentEvent | None:
    posters = [r.persona_id for r in reactions if r.chosen_action == "post_negative"]
    if len(posters) < 2:
        return None
    # check if any two posters are connected (amplification)
    connected_pairs = []
    for p in posters:
        for tgt in connections.get(p, []):
            if tgt in posters:
                connected_pairs.append(f"{p} → {tgt}")

    return EmergentEvent(
        name         = "pr_firestorm",
        description  = (
            f"{len(posters)} personas posting negatively"
            + (f", {len(connected_pairs)} connected pairs amplifying" if connected_pairs else "")
        ),
        causal_chain = posters + connected_pairs,
        severity     = "high" if connected_pairs else "medium",
    )


def _detect_silent_majority(
    actions: dict[str, str],
    archetypes: dict[str, str],
) -> EmergentEvent | None:
    action_counts = Counter(actions.values())
    wait_count    = action_counts.get("wait", 0)
    churn_count   = action_counts.get("churn", 0)
    total         = len(actions)

    if total == 0:
        return None

    # silent majority: >50% wait BUT churn exists underneath
    if wait_count / total > 0.5 and churn_count > 0:
        waiters = [pid for pid, a in actions.items() if a == "wait"]
        churners= [pid for pid, a in actions.items() if a == "churn"]
        return EmergentEvent(
            name         = "silent_majority",
            description  = (
                f"{wait_count}/{total} personas waiting — masking "
                f"{churn_count} churn(s). Deceptively calm surface."
            ),
            causal_chain = waiters + churners,
            severity     = "medium",
        )
    return None


def _detect_competitor_opportunity(
    actions: dict[str, str],
    archetypes: dict[str, str],
) -> EmergentEvent | None:
    churners     = [pid for pid, a in actions.items() if a == "churn"]
    competitors  = [pid for pid, arch in archetypes.items() if "competitor" in arch]

    if churners and competitors:
        return EmergentEvent(
            name         = "competitor_opportunity",
            description  = (
                f"{len(churners)} user(s) churning while "
                f"{len(competitors)} competitor agent(s) active — poaching risk."
            ),
            causal_chain = churners + competitors,
            severity     = "high",
        )
    return None


def _detect_enterprise_freeze(
    actions: dict[str, str],
    archetypes: dict[str, str],
) -> EmergentEvent | None:
    enterprise_waiters = [
        pid for pid, a in actions.items()
        if a == "wait" and "enterprise" in archetypes.get(pid, "")
    ]
    churners = [pid for pid, a in actions.items() if a == "churn"]

    if enterprise_waiters and churners:
        return EmergentEvent(
            name         = "enterprise_freeze",
            description  = (
                f"Enterprise buyer(s) ({enterprise_waiters}) stalled after "
                f"seeing {len(churners)} churn event(s). Deal at risk."
            ),
            causal_chain = enterprise_waiters + churners,
            severity     = "high",
        )
    return None


def _deterministic_pass(
    reactions: list[PersonaReaction],
    personas:  list[PersonaProfile],
) -> list[EmergentEvent]:
    actions     = _action_map(reactions)
    archetypes  = _archetype_map(personas)
    connections = _connections_map(personas)

    candidates = [
        _detect_viral_loop(actions, connections, "churn",
                           "negative_viral_loop",
                           "Churn cascading through social graph connections."),
        _detect_viral_loop(actions, connections, "upgrade",
                           "positive_viral_loop",
                           "Upgrade behaviour spreading through social graph."),
        _detect_pr_firestorm(reactions, connections),
        _detect_silent_majority(actions, archetypes),
        _detect_competitor_opportunity(actions, archetypes),
        _detect_enterprise_freeze(actions, archetypes),
    ]
    return [e for e in candidates if e is not None]


# ── Pass 2: LLM pattern detection ─────────────────────────────────────────────

SYSTEM_PROMPT_EMERGENT = """
You are analyzing a multi-agent stakeholder simulation log to identify
emergent, unexpected, or second-order behavioral effects.

You will receive:
- A list of persona reactions (action, emotional/rational response)
- An interaction log showing influence chains

Your job: identify emergent events NOT already in the provided list.
Focus on surprising, non-obvious second-order effects.

Return ONLY a valid JSON array — no markdown fences, no commentary.
Return an empty array [] if nothing new is found.

Each element:
{
  "name":         "<snake_case event name>",
  "description":  "<1-2 sentences explaining the emergent dynamic>",
  "causal_chain": [<persona_id or event label>, ...],
  "severity":     "low" | "medium" | "high"
}
""".strip()


def _llm_pass(
    reactions: list[PersonaReaction],
    interaction_log: list[str],
    already_found: list[EmergentEvent],
) -> list[EmergentEvent]:
    already_names = [e.name for e in already_found]

    reaction_summary = [
        {
            "persona_id": r.persona_id,
            "action":     r.chosen_action,
            "emotion":    r.emotional_response[:120],
            "rational":   r.rational_response[:120],
        }
        for r in reactions
    ]

    prompt = (
        f"REACTIONS:\n{json.dumps(reaction_summary, indent=2)}\n\n"
        f"INTERACTION LOG:\n" + "\n".join(interaction_log) + "\n\n"
        f"ALREADY DETECTED EVENTS (do not repeat): {json.dumps(already_names)}"
    )

    try:
        resp = _client.chat.completions.create(
            model=MODEL,
            temperature=0.5,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_EMERGENT},
                {"role": "user",   "content": prompt},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        items = json.loads(raw)
        return [
            EmergentEvent(
                name         = i.get("name", "unknown_event"),
                description  = i.get("description", ""),
                causal_chain = i.get("causal_chain", []),
                severity     = i.get("severity", "low"),
            )
            for i in items if isinstance(i, dict)
        ]
    except Exception:
        return []   # LLM pass is best-effort; never block the pipeline


# ── LangGraph node ─────────────────────────────────────────────────────────────
def emergent_tracker_node(state: SimulationState) -> SimulationState:
    if state.error:
        return state
    if not state.reactions:
        return state.model_copy(update={"error": "emergent_tracker: no reactions to analyze"})

    # Pass 1 — deterministic (always)
    det_events = _deterministic_pass(state.reactions, state.personas)

    # Pass 2 — LLM (always; finds novel patterns deterministic rules miss)
    llm_events = _llm_pass(state.reactions, state.interaction_log, det_events)

    all_events = det_events + llm_events

    return state.model_copy(update={"emergent_events": all_events, "error": ""})


# ── Quick local test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    from models.state import PersonaProfile, PersonaReaction, SimulationState

    personas = [
        PersonaProfile(
            id="power_user_01", name="Ethan Thompson", archetype="power_user",
            incentives=["retain API access"], emotional_baseline="ambitious",
            memory_seed="2-year free tier user.",
            social_connections=["casual_user_02", "churned_user_04"],
        ),
        PersonaProfile(
            id="casual_user_02", name="Lily Patel", archetype="casual_user",
            incentives=["free access"], emotional_baseline="relaxed",
            memory_seed="Logs in weekly.", social_connections=[],
        ),
        PersonaProfile(
            id="churned_user_04", name="Sophia Rodriguez", archetype="churned_user",
            incentives=["competitor migration"], emotional_baseline="frustrated",
            memory_seed="Already churned once.", social_connections=[],
        ),
        PersonaProfile(
            id="enterprise_buyer_03", name="Ryan Jenkins", archetype="enterprise_buyer",
            incentives=["scalable pricing"], emotional_baseline="pragmatic",
            memory_seed="Evaluating the product for a 200-seat deal.",
            social_connections=[],
        ),
    ]

    reactions = [
        PersonaReaction(
            persona_id="power_user_01", chosen_action="churn",
            emotional_response="I'm furious — two years of loyalty and now they want money.",
            rational_response="I'll move to the competitor's free plan immediately.",
            influence_targets=["casual_user_02", "churned_user_04"],
            raw_output="",
        ),
        PersonaReaction(
            persona_id="casual_user_02", chosen_action="churn",
            emotional_response="If even power users are leaving, this isn't worth it.",
            rational_response="The 14-day trial is too short to evaluate properly.",
            influence_targets=[], raw_output="",
        ),
        PersonaReaction(
            persona_id="churned_user_04", chosen_action="post_negative",
            emotional_response="Called it. They never cared about free users.",
            rational_response="I'll post my experience to warn others.",
            influence_targets=[], raw_output="",
        ),
        PersonaReaction(
            persona_id="enterprise_buyer_03", chosen_action="wait",
            emotional_response="Watching closely before committing to a 200-seat deal.",
            rational_response="If the user base is fragmenting, the risk is too high.",
            influence_targets=[], raw_output="",
        ),
    ]

    logs = [
        "[Round 1] Ethan Thompson → action=churn | influences=['casual_user_02','churned_user_04']",
        "[Round 2] Lily Patel → action=churn (influenced by Ethan's churn)",
        "[Round 2] Sophia Rodriguez → action=post_negative (influenced by Ethan's churn)",
    ]

    state  = SimulationState(personas=personas, reactions=reactions, interaction_log=logs)
    result = emergent_tracker_node(state)

    if result.error:
        print(f"❌ {result.error}")
    else:
        print(f"✅ {len(result.emergent_events)} emergent events detected:\n")
        for e in result.emergent_events:
            print(f"  [{e.severity.upper()}] {e.name}")
            print(f"    {e.description}")
            print(f"    causal chain: {e.causal_chain}\n")
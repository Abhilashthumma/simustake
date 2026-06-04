# ── agents/simulation_env.py ──────────────────────────────────────────────────
"""
SimulationEnvironment — LangGraph node (Step 4)

Input : SimulationState.personas + SimulationState.parsed_scenario
Output: SimulationState.reactions      (list[PersonaReaction])
        SimulationState.interaction_log (list[str])

Each persona runs a 3-step cycle:
  1. READ   — absorb the scenario + any upstream influence messages
  2. REACT  — form emotional + rational response
  3. ACT    — choose one action: churn | upgrade | post_negative |
                                  post_positive | wait

Influence propagation:
  After all personas react, agents with social_connections inject their
  action as an influence message into their targets' next context.
  This creates the chain-reaction effect the emergent tracker will analyze.
"""

from __future__ import annotations
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from groq import Groq

from models.state import PersonaProfile, PersonaReaction, SimulationState

load_dotenv()

_client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL   = "llama-3.3-70b-versatile"
VALID_ACTIONS = {"churn", "upgrade", "post_negative", "post_positive", "wait"}

# ── Prompt ────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are simulating a real person reacting to a business decision.
You will be given your persona profile, the business decision, and optionally
messages from people in your social circle who have already reacted.

Return ONLY valid JSON — no markdown fences, no commentary.

Schema:
{
  "emotional_response": "<1-2 sentences: raw gut reaction>",
  "rational_response":  "<1-2 sentences: reasoned analysis of impact on you>",
  "chosen_action":      "<one of: churn | upgrade | post_negative | post_positive | wait>",
  "influence_targets":  [<persona_id>, ...]  // from your social_connections list only
}

Action definitions:
- churn         : cancel / leave the product
- upgrade        : move to a paid plan
- post_negative  : publicly complain (social media, review site)
- post_positive  : publicly praise or defend the decision
- wait           : observe before acting

Rules:
- chosen_action must be exactly one of the five options above.
- influence_targets must be a subset of the social_connections you were given.
  If you choose not to influence anyone, return an empty list.
- Stay in character. Your emotional and rational responses must reflect your
  archetype, incentives, and emotional baseline.
""".strip()


def _build_user_prompt(
    persona: PersonaProfile,
    scenario: dict,
    influence_msgs: list[str],
) -> str:
    parts = [
        f"YOUR PERSONA:\n{json.dumps(persona.model_dump(), indent=2)}",
        f"\nBUSINESS DECISION (structured):\n{json.dumps(scenario, indent=2)}",
    ]
    if influence_msgs:
        parts.append(
            "\nMESSAGES FROM YOUR SOCIAL CIRCLE:\n"
            + "\n".join(f"- {m}" for m in influence_msgs)
        )
    return "\n".join(parts)


def _call_llm(persona: PersonaProfile, scenario: dict, influence_msgs: list[str]) -> dict:
    prompt = _build_user_prompt(persona, scenario, influence_msgs)
    resp = _client.chat.completions.create(
        model=MODEL,
        temperature=0.8,      # high temp → authentic individual variation
        max_tokens=512,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


def _safe_action(action: str) -> str:
    return action if action in VALID_ACTIONS else "wait"


def _run_persona(
    persona: PersonaProfile,
    scenario: dict,
    influence_msgs: list[str],
) -> PersonaReaction:
    """Run one persona's full reaction cycle. Called in parallel."""
    try:
        raw = _call_llm(persona, scenario, influence_msgs)
        return PersonaReaction(
            persona_id         = persona.id,
            emotional_response = raw.get("emotional_response", ""),
            rational_response  = raw.get("rational_response", ""),
            chosen_action      = _safe_action(raw.get("chosen_action", "wait")),
            influence_targets  = [
                t for t in raw.get("influence_targets", [])
                if t in persona.social_connections          # enforce graph boundary
            ],
            raw_output         = json.dumps(raw),
        )
    except Exception as e:
        return PersonaReaction(
            persona_id         = persona.id,
            emotional_response = "",
            rational_response  = "",
            chosen_action      = "wait",
            influence_targets  = [],
            raw_output         = f"ERROR: {e}",
        )


def _build_influence_messages(
    reactions: list[PersonaReaction],
    personas: list[PersonaProfile],
) -> dict[str, list[str]]:
    """
    After round 1, build influence message queues for round 2.
    Returns {persona_id: [influence_message, ...]}
    """
    persona_map = {p.id: p for p in personas}
    msgs: dict[str, list[str]] = {p.id: [] for p in personas}

    for r in reactions:
        p = persona_map.get(r.persona_id)
        if not p:
            continue
        for target_id in r.influence_targets:
            msg = (
                f"{p.name} ({p.archetype}, {p.emotional_baseline}) "
                f"just chose to '{r.chosen_action}': {r.emotional_response}"
            )
            if target_id in msgs:
                msgs[target_id].append(msg)

    return msgs


def _log_reactions(
    reactions: list[PersonaReaction],
    personas: list[PersonaProfile],
    round_num: int,
) -> list[str]:
    persona_map = {p.id: p for p in personas}
    logs = []
    for r in reactions:
        p = persona_map.get(r.persona_id, None)
        name = p.name if p else r.persona_id
        logs.append(
            f"[Round {round_num}] {name} ({r.persona_id}) → "
            f"action={r.chosen_action} | "
            f"influences={r.influence_targets} | "
            f"emotion='{r.emotional_response[:80]}...'"
        )
    return logs


# ── LangGraph node ─────────────────────────────────────────────────────────────
def simulation_env_node(state: SimulationState) -> SimulationState:
    """
    Two-round simulation:
      Round 1 — all personas react independently (parallel)
      Round 2 — influenced personas react again with social messages injected
    """
    if state.error:
        return state
    if not state.personas:
        return state.model_copy(update={"error": "simulation_env: no personas to simulate"})

    scenario  = state.parsed_scenario
    personas  = state.personas
    all_reactions: list[PersonaReaction] = []
    all_logs:      list[str]             = []

    # ── Round 1: independent reactions (parallel) ──────────────────────────
    round1_reactions: list[PersonaReaction] = []
    with ThreadPoolExecutor(max_workers=min(len(personas), 6)) as ex:
        futures = {
            ex.submit(_run_persona, p, scenario, []): p
            for p in personas
        }
        for fut in as_completed(futures):
            round1_reactions.append(fut.result())

    all_reactions.extend(round1_reactions)
    all_logs.extend(_log_reactions(round1_reactions, personas, round_num=1))

    # ── Round 2: influenced reactions ──────────────────────────────────────
    influence_msgs = _build_influence_messages(round1_reactions, personas)

    # only re-run personas that received influence messages
    influenced_personas = [
        p for p in personas if influence_msgs.get(p.id)
    ]

    if influenced_personas:
        round2_reactions: list[PersonaReaction] = []
        with ThreadPoolExecutor(max_workers=min(len(influenced_personas), 6)) as ex:
            futures = {
                ex.submit(_run_persona, p, scenario, influence_msgs[p.id]): p
                for p in influenced_personas
            }
            for fut in as_completed(futures):
                round2_reactions.append(fut.result())

        # round 2 reactions override round 1 for influenced personas
        overridden_ids = {r.persona_id for r in round2_reactions}
        all_reactions  = [r for r in all_reactions if r.persona_id not in overridden_ids]
        all_reactions.extend(round2_reactions)
        all_logs.extend(_log_reactions(round2_reactions, personas, round_num=2))

    return state.model_copy(update={
        "reactions":       all_reactions,
        "interaction_log": all_logs,
        "error":           "",
    })


# ── Quick local test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    from models.state import PersonaProfile, SimulationState

    personas = [
        PersonaProfile(
            id="power_user_01", name="Ethan Thompson", archetype="power_user",
            incentives=["retain API access", "avoid billing disruption"],
            emotional_baseline="ambitious",
            memory_seed="Has used the free tier for 2 years, relies on API daily.",
            social_connections=["casual_user_02", "churned_user_04"],
        ),
        PersonaProfile(
            id="casual_user_02", name="Lily Patel", archetype="casual_user",
            incentives=["free access", "simple navigation"],
            emotional_baseline="relaxed",
            memory_seed="Logs in once a week, uses basic features only.",
            social_connections=[],
        ),
        PersonaProfile(
            id="churned_user_04", name="Sophia Rodriguez", archetype="churned_user",
            incentives=["refund", "data export", "competitor migration"],
            emotional_baseline="frustrated",
            memory_seed="Cancelled 3 months ago after a billing issue.",
            social_connections=[],
        ),
    ]

    parsed = {
        "entities":          ["free tier", "14-day trial"],
        "stakes":            ["user trust", "MRR", "churn rate"],
        "ambiguities":       ["no grace period for existing users"],
        "affected_segments": ["power_user", "casual_user", "churned_user"],
        "constraints":       ["automatic migration"],
    }

    state  = SimulationState(personas=personas, parsed_scenario=parsed)
    result = simulation_env_node(state)

    if result.error:
        print(f"❌ {result.error}")
    else:
        print(f"✅ {len(result.reactions)} reactions across 2 rounds:\n")
        for log in result.interaction_log:
            print(" ", log)
        print()
        for r in result.reactions:
            print(f"  {r.persona_id} → {r.chosen_action}")
            print(f"    😤 {r.emotional_response}")
            print(f"    🧠 {r.rational_response}\n")
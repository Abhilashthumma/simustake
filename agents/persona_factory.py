
# ── agents/persona_factory.py ─────────────────────────────────────────────────
"""
PersonaFactoryAgent — LangGraph node (Step 3)

Input : SimulationState.parsed_scenario
Output: SimulationState.personas  (list[PersonaProfile])
        social graph stored in   social/influence_graph.py  (NetworkX)

For each affected_segment in parsed_scenario, the LLM generates a concrete
persona. The factory then wires them into a directed influence graph so the
simulation knows who nudges whom.
"""

from __future__ import annotations
import json
import os
import re
import uuid

from dotenv import load_dotenv
from groq import Groq

from models.state import PersonaProfile, SimulationState
from social.influence_graph import InfluenceGraph

load_dotenv()

_client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL   = "llama-3.3-70b-versatile"

# ── Prompt ────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are a product-strategy expert building stakeholder personas for a business
simulation. Given a parsed business scenario and a list of stakeholder archetypes,
generate one vivid, realistic persona per archetype.

Return ONLY a valid JSON array — no markdown fences, no commentary.

Each element must follow this exact schema:
{
  "id":                 "<archetype_snake_case>_<2-digit-number>",
  "name":               "<realistic full name>",
  "archetype":          "<archetype string from input>",
  "incentives":         [<string>, ...],   // 2-4 things this person wants
  "emotional_baseline": "<one word>",      // e.g. skeptical, hopeful, anxious
  "memory_seed":        "<1-2 sentences describing their history with the product>",
  "social_connections": []                 // leave empty — graph wired separately
}

Rules:
- Make each persona distinct and realistic. Give them concrete stakes.
- emotional_baseline must be a single word.
- incentives must be specific to THIS scenario, not generic.
- Never return null for any field.
""".strip()


def _build_persona_prompt(parsed: dict) -> str:
    segments   = parsed.get("affected_segments", [])
    stakes     = parsed.get("stakes", [])
    entities   = parsed.get("entities", [])
    return (
        f"Archetypes to generate: {json.dumps(segments)}\n"
        f"Scenario entities: {json.dumps(entities)}\n"
        f"Stakes in play: {json.dumps(stakes)}"
    )


def _call_llm(parsed: dict) -> list[dict]:
    prompt = _build_persona_prompt(parsed)
    resp = _client.chat.completions.create(
        model=MODEL,
        temperature=0.7,        # higher temp → distinct, varied personas
        max_tokens=2048,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    return json.loads(raw)


def _to_profiles(raw_personas: list[dict]) -> list[PersonaProfile]:
    profiles = []
    for p in raw_personas:
        # ensure id is unique even if LLM repeats one
        pid = p.get("id") or f"{p.get('archetype', 'unknown')}_{uuid.uuid4().hex[:4]}"
        profiles.append(PersonaProfile(
            id                = pid,
            name              = p.get("name", "Unknown"),
            archetype         = p.get("archetype", ""),
            incentives        = p.get("incentives", []),
            emotional_baseline= p.get("emotional_baseline", "neutral"),
            memory_seed       = p.get("memory_seed", ""),
            social_connections= [],   # filled in next step
        ))
    return profiles


def _wire_social_graph(profiles: list[PersonaProfile]) -> list[PersonaProfile]:
    """
    Build a directed influence graph with simple heuristic edges, then
    write social_connections back onto each PersonaProfile.

    Heuristic:
      - power_user     → casual_user, churned_user  (peer influence)
      - enterprise_*   → investor, internal_*        (B2B gravity)
      - competitor_*   → power_user, churned_user    (poaching)
      - internal_*     → all non-internal personas   (internal comms)
      - investor       → internal_*                  (board pressure)
    """
    graph = InfluenceGraph()
    for p in profiles:
        graph.add_persona(p.id, p.archetype)

    archetype_map: dict[str, list[str]] = {}
    for p in profiles:
        archetype_map.setdefault(p.archetype, []).append(p.id)

    def ids_matching(prefix: str) -> list[str]:
        return [pid for arch, pids in archetype_map.items()
                if arch.startswith(prefix) for pid in pids]

    edge_rules = [
        ("power_user",        ["casual_user", "churned_user"]),
        ("enterprise",        ["investor", "internal"]),
        ("competitor",        ["power_user", "churned_user"]),
        ("internal",          ["power_user", "casual_user",
                               "enterprise", "churned_user", "investor"]),
        ("investor",          ["internal"]),
    ]

    for src_prefix, tgt_prefixes in edge_rules:
        for src_id in ids_matching(src_prefix):
            for tgt_prefix in tgt_prefixes:
                for tgt_id in ids_matching(tgt_prefix):
                    if src_id != tgt_id:
                        graph.add_edge(src_id, tgt_id)

    # write connections back to profiles
    updated = []
    for p in profiles:
        connections = graph.get_influenced_by(p.id)
        updated.append(p.model_copy(update={"social_connections": connections}))

    return updated


# ── LangGraph node ─────────────────────────────────────────────────────────────
def persona_factory_node(state: SimulationState) -> SimulationState:
    if state.error:
        return state
    if not state.parsed_scenario:
        return state.model_copy(update={"error": "persona_factory: parsed_scenario is empty"})

    try:
        raw      = _call_llm(state.parsed_scenario)
        profiles = _to_profiles(raw)
        profiles = _wire_social_graph(profiles)
        return state.model_copy(update={"personas": profiles, "error": ""})

    except json.JSONDecodeError as e:
        return state.model_copy(update={"error": f"PersonaFactory JSON error: {e}"})
    except Exception as e:
        return state.model_copy(update={"error": f"PersonaFactory error: {e}"})


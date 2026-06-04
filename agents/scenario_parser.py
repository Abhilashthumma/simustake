# ── agents/scenario_parser.py ─────────────────────────────────────────────────
"""
ScenarioParserAgent — LangGraph node (Step 2)

Input : SimulationState.raw_scenario  (plain English decision)
Output: SimulationState.parsed_scenario (structured dict)

parsed_scenario shape:
{
  "entities":           ["free tier", "14-day trial", "pricing page"],
  "stakes":             ["user trust", "MRR", "support load"],
  "ambiguities":        ["no mention of grandfathering existing users"],
  "affected_segments":  ["power_user", "casual_user", "enterprise_buyer", ...],
  "constraints":        ["must ship Q3", "no refunds policy"]
}
"""

from __future__ import annotations
import json
import os
import re

from dotenv import load_dotenv
from groq import Groq

from models.state import SimulationState

load_dotenv()

# ── Groq client (shared across agents) ───────────────────────────────────────
_client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL   = "llama-3.3-70b-versatile"

# ── Prompt ────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are a business-decision analyst. Your job is to parse a plain-English
business decision into a structured JSON object for a stakeholder simulation.

Return ONLY valid JSON — no markdown fences, no commentary.

The JSON must follow this exact schema:
{
  "entities":          [<string>, ...],   // nouns: products, policies, teams, metrics
  "stakes":            [<string>, ...],   // what is at risk for real people
  "ambiguities":       [<string>, ...],   // missing info that could change outcomes
  "affected_segments": [<string>, ...],   // user/buyer/employee archetypes affected
  "constraints":       [<string>, ...]    // known limits: legal, timeline, budget
}

Rules:
- affected_segments must be concrete archetypes, e.g. "power_user", "enterprise_buyer",
  "churned_user", "internal_skeptic", "competitor_analyst", "investor".
  Always include at least 4 segments.
- ambiguities must be real unknowns in the scenario, not generic filler.
- If a field has nothing meaningful, return an empty list — never null.
""".strip()


def _call_llm(scenario: str) -> dict:
    """Call Groq and return parsed JSON. Raises on bad response."""
    resp = _client.chat.completions.create(
        model=MODEL,
        temperature=0.2,          # low temp → deterministic parsing
        max_tokens=1024,
        messages=[
            {"role": "system",  "content": SYSTEM_PROMPT},
            {"role": "user",    "content": f"Business decision:\n{scenario}"},
        ],
    )
    raw = resp.choices[0].message.content.strip()

    # strip accidental markdown fences if model slips
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()

    return json.loads(raw)


def _validate(parsed: dict) -> dict:
    """Ensure all required keys are present; fill missing with empty lists."""
    required = ["entities", "stakes", "ambiguities", "affected_segments", "constraints"]
    for key in required:
        if key not in parsed or not isinstance(parsed[key], list):
            parsed[key] = []
    return parsed


# ── LangGraph node ────────────────────────────────────────────────────────────
def scenario_parser_node(state: SimulationState) -> SimulationState:
    """
    LangGraph node — reads state.raw_scenario, writes state.parsed_scenario.
    Returns the full updated state (LangGraph convention).
    """
    if not state.raw_scenario.strip():
        return state.model_copy(update={"error": "raw_scenario is empty"})

    try:
        parsed = _call_llm(state.raw_scenario)
        parsed = _validate(parsed)
        return state.model_copy(update={"parsed_scenario": parsed, "error": ""})

    except json.JSONDecodeError as e:
        return state.model_copy(update={"error": f"ScenarioParser JSON error: {e}"})
    except Exception as e:
        return state.model_copy(update={"error": f"ScenarioParser error: {e}"})


# ── Quick local test (run: python -m agents.scenario_parser) ──────────────────
if __name__ == "__main__":
    from models.state import SimulationState

    scenario = (
        "We're removing the free tier and replacing it with a 14-day trial. "
        "Existing free users will be migrated automatically with no grace period."
    )

    state = SimulationState(raw_scenario=scenario)
    result = scenario_parser_node(state)

    if result.error:
        print(f"❌ Error: {result.error}")
    else:
        print("✅ Parsed scenario:\n")
        print(json.dumps(result.parsed_scenario, indent=2))
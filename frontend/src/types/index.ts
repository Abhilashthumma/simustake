

export interface Persona {
  id:                 string;
  name:               string;
  archetype:          string;
  emotional_baseline: string;
  chosen_action:      string;
}

export interface EmergentEvent {
  name:        string;
  severity:    "low" | "medium" | "high";
  description: string;
}

export interface SimulationResult {
  simulation_id:        string;
  confidence_score:     number;
  churn_pct_range:      [number, number];
  revenue_impact_range: [number, number];
  pr_risk_score:        number;
  unexpected_effects:   string[];
  recommendations:      string[];
  citations:            Record<string, string>;
  emergent_events:      EmergentEvent[];
  personas:             Persona[];
  rerun_count:          number;
  error:                string;
}


"use client";
import type { SimulationResult } from "@/types";
import PersonaCard    from "./PersonaCard";
import EmergentBadge  from "./EmergentBadge";

const fmt = (n: number) =>
  (n < 0 ? "-$" : "$") + Math.abs(n).toLocaleString();

const riskColor = (s: number) =>
  s >= 0.7 ? "text-red-400" : s >= 0.4 ? "text-yellow-400" : "text-green-400";

export default function OutcomeReport({ result }: { result: SimulationResult }) {
  const r = result;
  return (
    <div className="space-y-6">

      {/* meta bar */}
      <div className="flex flex-wrap gap-3 text-xs text-gray-400">
        <span className="bg-gray-800 rounded-full px-3 py-1">
          🆔 {r.simulation_id.slice(0, 8)}
        </span>
        <span className="bg-gray-800 rounded-full px-3 py-1">
          📈 confidence {(r.confidence_score * 100).toFixed(0)}%
        </span>
        {r.rerun_count > 0 && (
          <span className="bg-indigo-900/50 border border-indigo-700 rounded-full px-3 py-1">
            🔁 refined {r.rerun_count}×
          </span>
        )}
      </div>

      {/* metric cards */}
      <div className="grid grid-cols-3 gap-3">
        <MetricCard label="Churn range"
          value={`${r.churn_pct_range[0]}% – ${r.churn_pct_range[1]}%`}
          sub="of affected users" color="text-orange-400" />
        <MetricCard label="Revenue impact"
          value={`${fmt(r.revenue_impact_range[0])} – ${fmt(r.revenue_impact_range[1])}`}
          sub="per month" color="text-red-400" />
        <MetricCard label="PR risk"
          value={(r.pr_risk_score * 100).toFixed(0) + "%"}
          sub="crisis probability"
          color={riskColor(r.pr_risk_score)} />
      </div>

      {/* emergent events */}
      {r.emergent_events.length > 0 && (
        <Section title="⚡ Emergent Events">
          <div className="flex flex-wrap gap-2">
            {r.emergent_events.map(e => <EmergentBadge key={e.name} event={e} />)}
          </div>
        </Section>
      )}

      {/* persona cards */}
      <Section title="🧬 Personas">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {r.personas.map(p => <PersonaCard key={p.id} persona={p} />)}
        </div>
      </Section>

      {/* unexpected effects */}
      <Section title="🔍 Unexpected Effects">
        <ul className="space-y-2">
          {r.unexpected_effects.map((e, i) => (
            <li key={i} className="flex gap-2 text-sm text-gray-300">
              <span className="text-yellow-500 mt-0.5">•</span>
              <CitedText text={e} citations={r.citations} />
            </li>
          ))}
        </ul>
      </Section>

      {/* recommendations */}
      <Section title="✅ Recommendations">
        <ol className="space-y-2 list-decimal list-inside">
          {r.recommendations.map((rec, i) => (
            <li key={i} className="text-sm text-gray-300">
              <CitedText text={rec} citations={r.citations} />
            </li>
          ))}
        </ol>
      </Section>

    </div>
  );
}

function MetricCard({ label, value, sub, color }: {
  label: string; value: string; sub: string; color: string;
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-1">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-lg font-bold ${color}`}>{value}</p>
      <p className="text-xs text-gray-600">{sub}</p>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-3">
      <h2 className="text-sm font-semibold text-gray-300">{title}</h2>
      {children}
    </div>
  );
}

function CitedText({ text, citations }: { text: string; citations: Record<string, string> }) {
  // find if any citation key appears in this text
  const match = Object.entries(citations).find(([key]) =>
    text.toLowerCase().includes(key.toLowerCase())
  );
  if (!match) return <span>{text}</span>;
  const [, persona] = match;
  return (
    <span>
      {text}
      <span className="ml-2 text-xs bg-indigo-900/60 border border-indigo-700
                        rounded px-1.5 py-0.5 text-indigo-300 font-mono">
        ← {persona}
      </span>
    </span>
  );
}
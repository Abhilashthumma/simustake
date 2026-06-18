"use client";
import type { SimulationResult } from "@/types";
import PersonaCard   from "./PersonaCard";
import EmergentBadge from "./EmergentBadge";

const fmt = (n: number) =>
  (n < 0 ? "-$" : "+$") + Math.abs(Math.round(n)).toLocaleString();

function RiskBar({ score }: { score: number }) {
  const pct  = Math.round(score * 100);
  const color = score >= 0.7 ? "bg-red-500" : score >= 0.4 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm font-mono font-medium">{pct}%</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5 space-y-4">
      <h2 className="text-xs font-medium text-gray-500 uppercase tracking-widest">{title}</h2>
      {children}
    </div>
  );
}

function CitedText({ text, citations }: { text: string; citations: Record<string, string> }) {
  const match = Object.entries(citations).find(([k]) =>
    text.toLowerCase().includes(k.toLowerCase())
  );
  return (
    <span>
      {text}
      {match && (
        <span className="ml-2 inline-flex items-center gap-1 text-[11px] bg-violet-900/40
                         border border-violet-700/40 rounded-md px-1.5 py-0.5
                         text-violet-400 font-mono align-middle">
          ← {match[1]}
        </span>
      )}
    </span>
  );
}

export default function OutcomeReport({ result: r }: { result: SimulationResult }) {
  return (
    <div className="space-y-4">

      {/* meta strip */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 font-mono text-gray-500">
          id: {r.simulation_id.slice(0, 10)}
        </span>
        <span className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-gray-400">
          confidence: <span className="text-white font-medium">{Math.round(r.confidence_score * 100)}%</span>
        </span>
        {r.rerun_count > 0 && (
          <span className="bg-violet-900/30 border border-violet-700/40 rounded-lg px-3 py-1.5 text-violet-300">
            refined {r.rerun_count}×
          </span>
        )}
        <span className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-gray-400">
          {r.personas.length} personas · {r.emergent_events.length} events
        </span>
      </div>

      {/* metric cards */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 space-y-2">
          <p className="text-xs text-gray-600 uppercase tracking-widest">Churn range</p>
          <p className="text-2xl font-semibold text-orange-400 tracking-tight">
            {r.churn_pct_range[0]}–{r.churn_pct_range[1]}%
          </p>
          <p className="text-xs text-gray-600">of affected users</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 space-y-2">
          <p className="text-xs text-gray-600 uppercase tracking-widest">Revenue / mo</p>
          <p className="text-2xl font-semibold text-red-400 tracking-tight">
            {fmt(r.revenue_impact_range[0])}
          </p>
          <p className="text-xs text-gray-600">to {fmt(r.revenue_impact_range[1])}</p>
        </div>
        <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 space-y-2">
          <p className="text-xs text-gray-600 uppercase tracking-widest">PR risk</p>
          <div className="pt-1"><RiskBar score={r.pr_risk_score} /></div>
          <p className="text-xs text-gray-600">crisis probability</p>
        </div>
      </div>

      {/* emergent events */}
      {r.emergent_events.length > 0 && (
        <Section title="Emergent events">
          <div className="flex flex-wrap gap-2">
            {r.emergent_events.map(e => <EmergentBadge key={e.name} event={e} />)}
          </div>
        </Section>
      )}

      {/* personas */}
      <Section title="Stakeholder personas">
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {r.personas.map(p => <PersonaCard key={p.id} persona={p} />)}
        </div>
      </Section>

      {/* unexpected effects */}
      <Section title="Unexpected effects">
        <ul className="space-y-3">
          {r.unexpected_effects.map((e, i) => (
            <li key={i} className="flex gap-3 text-sm text-gray-300 leading-relaxed">
              <span className="text-violet-500 shrink-0 mt-1">◆</span>
              <CitedText text={e} citations={r.citations} />
            </li>
          ))}
        </ul>
      </Section>

      {/* recommendations */}
      <Section title="Recommendations">
        <ol className="space-y-3">
          {r.recommendations.map((rec, i) => (
            <li key={i} className="flex gap-3 text-sm text-gray-300 leading-relaxed">
              <span className="text-gray-600 shrink-0 font-mono mt-0.5 w-4">{i + 1}.</span>
              <CitedText text={rec} citations={r.citations} />
            </li>
          ))}
        </ol>
      </Section>

    </div>
  );
}
"use client";
import { useState } from "react";
import ScenarioForm   from "@/components/ScenarioForm";
import SimulationFeed from "@/components/SimulationFeed";
import OutcomeReport  from "@/components/OutcomeReport";
import type { SimulationResult } from "@/types";

export default function Home() {
  const [status, setStatus] = useState<"idle"|"running"|"done"|"error">("idle");
  const [log,    setLog]    = useState<string[]>([]);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [errMsg, setErrMsg] = useState("");

  async function handleSubmit(scenario: string) {
    setStatus("running"); setLog([]); setResult(null); setErrMsg("");
    const steps = [
      "Parsing scenario entities and stakes…",
      "Spawning stakeholder persona agents…",
      "Running round 1 — independent reactions…",
      "Running round 2 — social influence propagation…",
      "Detecting emergent behaviors and chain reactions…",
      "Scoring simulation confidence…",
      "Generating cited outcome report…",
    ];
    let i = 0;
    const iv = setInterval(() => { if (i < steps.length) setLog(l => [...l, steps[i++]]); }, 5000);
    try {
      const res  = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario }),
      });
      clearInterval(iv);
      if (!res.ok) throw new Error(`API ${res.status}`);
      const data: SimulationResult = await res.json();
      if (data.error) throw new Error(data.error);
      setLog(l => [...l, "Simulation complete."]);
      setResult(data); setStatus("done");
    } catch (e: unknown) {
      clearInterval(iv);
      setErrMsg(e instanceof Error ? e.message : "Unknown error");
      setStatus("error");
    }
  }

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-gray-100">
      {/* hero header */}
      <div className="border-b border-white/5 bg-[#0d0d14]">
        <div className="max-w-4xl mx-auto px-6 py-8 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="w-8 h-8 rounded-lg bg-violet-600 flex items-center justify-center text-sm font-bold">S</div>
              <span className="font-semibold text-lg tracking-tight">SimuStake</span>
              <span className="text-[11px] bg-violet-900/50 text-violet-300 border border-violet-700/50 rounded-full px-2 py-0.5">beta</span>
            </div>
            <p className="text-sm text-gray-500">Multi-agent stakeholder simulation engine</p>
          </div>
          <div className="text-right hidden sm:block">
            <p className="text-xs text-gray-600">Powered by</p>
            <p className="text-xs text-gray-400 font-mono">LangGraph · Llama 3.3 · Groq</p>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-10 space-y-8">
        {status === "idle" && (
          <div className="text-center py-6 space-y-3">
            <h1 className="text-3xl font-semibold tracking-tight">What decision are you about to ship?</h1>
            <p className="text-gray-400 max-w-xl mx-auto text-sm leading-relaxed">
              Describe it in plain English. SimuStake spawns AI stakeholder agents, runs a social-influence simulation, and returns a cited outcome report with churn %, revenue impact, and PR risk.
            </p>
          </div>
        )}

        <ScenarioForm onSubmit={handleSubmit} disabled={status === "running"} />

        {status === "error" && (
          <div className="flex gap-3 items-start bg-red-950/40 border border-red-800/50 rounded-xl p-4 text-sm text-red-300">
            <span className="mt-0.5 shrink-0">⚠</span>
            <span>{errMsg}</span>
          </div>
        )}

        {(status === "running" || status === "done") && (
          <SimulationFeed log={log} running={status === "running"} />
        )}

        {result && <OutcomeReport result={result} />}
      </div>
    </main>
  );
}
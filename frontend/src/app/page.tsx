
"use client";

import { useState } from "react";
import ScenarioForm  from "@/components/ScenarioForm";
import SimulationFeed from "@/components/SimulationFeed";
import OutcomeReport  from "@/components/OutcomeReport";
import type { SimulationResult } from "@/types";

export default function Home() {
  const [status,  setStatus]  = useState<"idle"|"running"|"done"|"error">("idle");
  const [log,     setLog]     = useState<string[]>([]);
  const [result,  setResult]  = useState<SimulationResult | null>(null);
  const [errMsg,  setErrMsg]  = useState("");

  async function handleSubmit(scenario: string) {
    setStatus("running");
    setLog([]);
    setResult(null);
    setErrMsg("");

    const steps = [
      "🔍 Parsing scenario...",
      "🧬 Spawning persona agents...",
      "⚡ Running simulation rounds...",
      "🌀 Detecting emergent behaviors...",
      "📊 Scoring confidence...",
      "📋 Generating outcome report...",
    ];

    // stream fake progress while real API runs
    let i = 0;
    const interval = setInterval(() => {
      if (i < steps.length) setLog(l => [...l, steps[i++]]);
    }, 4000);

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/simulate`,
        {
          method:  "POST",
          headers: { "Content-Type": "application/json" },
          body:    JSON.stringify({ scenario }),
        }
      );
      clearInterval(interval);

      if (!res.ok) throw new Error(`API error ${res.status}`);
      const data: SimulationResult = await res.json();

      if (data.error) throw new Error(data.error);

      setLog(l => [...l, "✅ Simulation complete."]);
      setResult(data);
      setStatus("done");
    } catch (e: unknown) {
      clearInterval(interval);
      setErrMsg(e instanceof Error ? e.message : "Unknown error");
      setStatus("error");
    }
  }

  return (
    <main className="min-h-screen bg-gray-950 text-gray-100 px-4 py-10">
      <div className="max-w-3xl mx-auto space-y-8">

        {/* header */}
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-bold tracking-tight">
            SimuStake <span className="text-2xl">🎭</span>
          </h1>
          <p className="text-gray-400 text-sm">
            Multi-agent stakeholder simulation engine
          </p>
        </div>

        <ScenarioForm onSubmit={handleSubmit} disabled={status === "running"} />

        {status === "error" && (
          <div className="bg-red-900/40 border border-red-700 rounded-xl p-4 text-red-300 text-sm">
            ❌ {errMsg}
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


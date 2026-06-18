"use client";
import { useEffect, useRef } from "react";

const ICONS: Record<string, string> = {
  "Parsing scenario":     "◈",
  "Spawning stakeholder": "◉",
  "Running round 1":      "▶",
  "Running round 2":      "▶▶",
  "Detecting emergent":   "⬡",
  "Scoring simulation":   "◎",
  "Generating cited":     "◆",
  "Simulation complete":  "✦",
};

function getIcon(line: string) {
  for (const [k, v] of Object.entries(ICONS)) {
    if (line.startsWith(k)) return v;
  }
  return "·";
}

export default function SimulationFeed({
  log, running,
}: { log: string[]; running: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { ref.current?.scrollTo(0, ref.current.scrollHeight); }, [log]);

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] overflow-hidden">
      {/* header bar */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/5 bg-white/[0.02]">
        <div className="flex gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-white/10" />
          <div className="w-2.5 h-2.5 rounded-full bg-white/10" />
          <div className="w-2.5 h-2.5 rounded-full bg-white/10" />
        </div>
        <span className="text-xs text-gray-600 font-mono ml-1">simulation pipeline</span>
        {running && (
          <span className="ml-auto flex items-center gap-1.5 text-xs text-violet-400">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
            running
          </span>
        )}
        {!running && log.length > 0 && (
          <span className="ml-auto text-xs text-emerald-400">complete</span>
        )}
      </div>

      {/* log lines */}
      <div ref={ref} className="p-4 space-y-2 max-h-48 overflow-y-auto">
        {log.map((line, i) => (
          <div key={i} className={`flex items-start gap-3 text-sm font-mono
            ${line.startsWith("Simulation") ? "text-emerald-400" : "text-gray-400"}`}>
            <span className="text-gray-600 shrink-0 w-4 text-center mt-px">{getIcon(line)}</span>
            <span>{line}</span>
          </div>
        ))}
        {running && (
          <div className="flex items-center gap-3 text-sm font-mono text-gray-600">
            <span className="w-4 text-center">·</span>
            <span className="animate-pulse">processing…</span>
          </div>
        )}
      </div>
    </div>
  );
}
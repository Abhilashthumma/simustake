
"use client";

export default function SimulationFeed({
  log, running,
}: { log: string[]; running: boolean }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4
                    font-mono text-xs space-y-1">
      {log.map((line, i) => (
        <div key={i} className="text-green-400">{line}</div>
      ))}
      {running && (
        <div className="text-gray-500 animate-pulse">▌</div>
      )}
    </div>
  );
}

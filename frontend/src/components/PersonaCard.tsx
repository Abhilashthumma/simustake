
"use client";
import type { Persona } from "@/types";

const ACTION_STYLE: Record<string, string> = {
  churn:         "bg-red-900/40 text-red-300 border-red-800",
  upgrade:       "bg-green-900/40 text-green-300 border-green-800",
  post_negative: "bg-orange-900/40 text-orange-300 border-orange-800",
  post_positive: "bg-blue-900/40 text-blue-300 border-blue-800",
  wait:          "bg-gray-800 text-gray-400 border-gray-700",
};

const ACTION_ICON: Record<string, string> = {
  churn: "💨", upgrade: "⬆️", post_negative: "📢",
  post_positive: "👍", wait: "⏳",
};

export default function PersonaCard({ persona: p }: { persona: Persona }) {
  const style = ACTION_STYLE[p.chosen_action] ?? ACTION_STYLE.wait;
  const icon  = ACTION_ICON[p.chosen_action]  ?? "❓";
  return (
    <div className={`border rounded-xl p-3 space-y-2 ${style}`}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">{p.name}</span>
        <span className="text-lg">{icon}</span>
      </div>
      <p className="text-xs opacity-70">{p.archetype.replace(/_/g, " ")}</p>
      <p className="text-xs opacity-60 italic">{p.emotional_baseline}</p>
      <p className="text-xs font-mono">{p.chosen_action}</p>
    </div>
  );
}


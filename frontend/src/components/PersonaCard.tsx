"use client";
import type { Persona } from "@/types";

const ACTION_CONFIG: Record<string, { color: string; bg: string; border: string; icon: string; label: string }> = {
  churn:         { color: "text-red-400",     bg: "bg-red-950/40",    border: "border-red-800/50",    icon: "→", label: "churned"       },
  upgrade:       { color: "text-emerald-400", bg: "bg-emerald-950/40",border: "border-emerald-800/50",icon: "↑", label: "upgraded"      },
  post_negative: { color: "text-orange-400",  bg: "bg-orange-950/40", border: "border-orange-800/50", icon: "!", label: "posted negative"},
  post_positive: { color: "text-blue-400",    bg: "bg-blue-950/40",   border: "border-blue-800/50",   icon: "✓", label: "posted positive"},
  wait:          { color: "text-gray-400",    bg: "bg-white/[0.02]",  border: "border-white/10",      icon: "…", label: "waiting"       },
};

const ARCHETYPE_INITIALS: Record<string, string> = {
  power_user:        "PU",
  casual_user:       "CU",
  enterprise_buyer:  "EB",
  churned_user:      "CH",
  competitor_analyst:"CA",
  investor:          "IN",
  internal_skeptic:  "IS",
};

export default function PersonaCard({ persona: p }: { persona: Persona }) {
  const cfg      = ACTION_CONFIG[p.chosen_action] ?? ACTION_CONFIG.wait;
  const initials = ARCHETYPE_INITIALS[p.archetype] ?? p.archetype.slice(0, 2).toUpperCase();

  return (
    <div className={`rounded-xl border ${cfg.border} ${cfg.bg} p-3.5 space-y-3`}>
      {/* avatar + name */}
      <div className="flex items-center gap-2.5">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center
                         text-xs font-semibold shrink-0 ${cfg.bg} border ${cfg.border} ${cfg.color}`}>
          {initials}
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-200 truncate">{p.name}</p>
          <p className="text-xs text-gray-600 truncate">{p.archetype.replace(/_/g, " ")}</p>
        </div>
      </div>

      {/* divider */}
      <div className="border-t border-white/5" />

      {/* mood + action */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500 italic">{p.emotional_baseline}</span>
        <span className={`flex items-center gap-1 text-xs font-mono font-medium ${cfg.color}`}>
          <span>{cfg.icon}</span>
          <span>{cfg.label}</span>
        </span>
      </div>
    </div>
  );
}
"use client";
import { useState, useRef, useEffect } from "react";
import type { EmergentEvent } from "@/types";

const SEV_CONFIG = {
  high:   { badge: "bg-red-950/60 border-red-800/60 text-red-400",   dot: "bg-red-500"   },
  medium: { badge: "bg-amber-950/60 border-amber-800/60 text-amber-400", dot: "bg-amber-500" },
  low:    { badge: "bg-white/5 border-white/10 text-gray-500",        dot: "bg-gray-600"  },
};

export default function EmergentBadge({ event: e }: { event: EmergentEvent }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const cfg = SEV_CONFIG[e.severity] ?? SEV_CONFIG.low;

  useEffect(() => {
    function handler(ev: MouseEvent) {
      if (ref.current && !ref.current.contains(ev.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className={`flex items-center gap-1.5 text-xs border rounded-lg px-2.5 py-1.5
                    font-mono transition-all hover:opacity-80 ${cfg.badge}`}>
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${cfg.dot}`} />
        {e.name.replace(/_/g, " ")}
      </button>

      {open && (
        <div className="absolute z-20 top-9 left-0 w-72
                        bg-[#13131f] border border-white/10 rounded-xl p-4
                        shadow-2xl shadow-black/50 space-y-2">
          <div className="flex items-center justify-between">
            <span className={`text-xs font-mono font-medium ${cfg.badge.split(" ").pop()}`}>
              {e.severity} severity
            </span>
            <button onClick={() => setOpen(false)}
              className="text-gray-600 hover:text-gray-400 text-xs">✕</button>
          </div>
          <p className="text-xs text-gray-400 leading-relaxed">{e.description}</p>
        </div>
      )}
    </div>
  );
}
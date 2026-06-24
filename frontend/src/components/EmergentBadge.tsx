
"use client";
import { useState } from "react";
import type { EmergentEvent } from "@/types";

const SEV: Record<string, string> = {
  high:   "bg-red-900/50 border-red-700 text-red-300",
  medium: "bg-yellow-900/50 border-yellow-700 text-yellow-300",
  low:    "bg-gray-800 border-gray-700 text-gray-400",
};

export default function EmergentBadge({ event: e }: { event: EmergentEvent }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className={`text-xs border rounded-full px-3 py-1 font-mono
                    transition hover:opacity-80 ${SEV[e.severity]}`}
      >
        {e.name.replace(/_/g, " ")}
      </button>
      {open && (
        <div className="absolute z-10 top-8 left-0 w-64 bg-gray-900
                        border border-gray-700 rounded-xl p-3 text-xs
                        text-gray-300 shadow-xl">
          <p className="font-semibold mb-1 capitalize">{e.severity} severity</p>
          <p>{e.description}</p>
        </div>
      )}
    </div>
  );
}
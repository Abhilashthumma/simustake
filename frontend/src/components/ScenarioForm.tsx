

"use client";
import { useState } from "react";

const EXAMPLES = [
  "We're removing the free tier and replacing it with a 14-day trial.",
  "We're raising prices by 40% for all plans starting next month.",
  "We're shutting down the mobile app and going web-only.",
];

export default function ScenarioForm({
  onSubmit, disabled,
}: { onSubmit: (s: string) => void; disabled: boolean }) {
  const [text, setText] = useState("");

  return (
    <div className="space-y-3">
      <textarea
        className="w-full bg-gray-900 border border-gray-700 rounded-xl p-4
                   text-sm text-gray-100 placeholder-gray-500 resize-none
                   focus:outline-none focus:ring-2 focus:ring-indigo-500
                   disabled:opacity-50"
        rows={4}
        placeholder="Describe your business decision in plain English…"
        value={text}
        onChange={e => setText(e.target.value)}
        disabled={disabled}
      />

      {/* example pills */}
      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map(ex => (
          <button key={ex}
            onClick={() => setText(ex)}
            disabled={disabled}
            className="text-xs bg-gray-800 hover:bg-gray-700 border border-gray-700
                       rounded-full px-3 py-1 text-gray-400 hover:text-gray-200
                       transition disabled:opacity-40"
          >
            {ex.slice(0, 45)}…
          </button>
        ))}
      </div>

      <button
        onClick={() => text.trim() && onSubmit(text.trim())}
        disabled={disabled || !text.trim()}
        className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500
                   font-semibold text-sm tracking-wide transition
                   disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {disabled ? "Simulating…" : "Run Simulation →"}
      </button>
    </div>
  );
}

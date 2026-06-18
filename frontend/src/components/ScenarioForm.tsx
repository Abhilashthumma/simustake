"use client";
import { useState } from "react";

const EXAMPLES = [
  "We're removing the free tier and replacing it with a 14-day trial. Existing users get no grace period.",
  "We're raising prices by 40% across all plans starting next month with 2 weeks notice.",
  "We're shutting down the mobile app and going web-only in 60 days.",
  "We're acquiring a competitor and merging both products into one platform.",
];

export default function ScenarioForm({
  onSubmit, disabled,
}: { onSubmit: (s: string) => void; disabled: boolean }) {
  const [text, setText] = useState("");

  return (
    <div className="space-y-4">
      {/* example pills */}
      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((ex, i) => (
          <button key={i} onClick={() => setText(ex)} disabled={disabled}
            className="text-xs bg-white/5 hover:bg-white/10 border border-white/10
                       rounded-full px-3 py-1.5 text-gray-400 hover:text-gray-200
                       transition-all disabled:opacity-40 text-left">
            {ex.slice(0, 48)}…
          </button>
        ))}
      </div>

      {/* textarea */}
      <div className="relative">
        <textarea
          rows={4}
          value={text}
          onChange={e => setText(e.target.value)}
          disabled={disabled}
          placeholder="Describe your business decision in plain English…"
          className="w-full bg-white/[0.03] border border-white/10 rounded-2xl p-4 pr-32
                     text-sm text-gray-100 placeholder-gray-600 resize-none
                     focus:outline-none focus:ring-1 focus:ring-violet-500/50
                     focus:border-violet-500/50 transition-all disabled:opacity-50"
        />
        <button
          onClick={() => text.trim() && onSubmit(text.trim())}
          disabled={disabled || !text.trim()}
          className="absolute bottom-3 right-3 px-4 py-2 rounded-xl
                     bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium
                     transition-all disabled:opacity-40 disabled:cursor-not-allowed
                     flex items-center gap-2">
          {disabled
            ? <><span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />Simulating</>
            : <>Run →</>}
        </button>
      </div>
    </div>
  );
}
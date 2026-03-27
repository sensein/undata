"use client";

import { useState } from "react";

interface EvidencePanelProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  context: Record<string, any>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  llmVerification?: Record<string, any> | null;
}

export function EvidencePanel({ context, llmVerification }: EvidencePanelProps) {
  const [showFull, setShowFull] = useState(false);

  const candidates = (context.candidates ?? context.candidate_matches ?? []) as Array<{
    term_label?: string;
    ontology?: string;
    score?: number;
    relation?: string;
  }>;

  return (
    <div className="border rounded-lg p-4 bg-gray-50 space-y-4">
      {/* Match candidates */}
      {candidates.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold mb-2">Match Candidates</h4>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 text-xs">
                <th className="pb-1">Term</th>
                <th className="pb-1">Ontology</th>
                <th className="pb-1">Score</th>
                <th className="pb-1">Relation</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c, i) => (
                <tr key={i} className="border-t">
                  <td className="py-1 font-medium">{c.term_label ?? "—"}</td>
                  <td className="py-1 text-gray-600">{c.ontology ?? "—"}</td>
                  <td className="py-1 font-mono">{c.score != null ? Number(c.score).toFixed(3) : "—"}</td>
                  <td className="py-1 text-gray-600">{c.relation ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* LLM Verification */}
      {llmVerification && (
        <div>
          <h4 className="text-sm font-semibold mb-2">LLM Verification</h4>
          <div className="text-sm space-y-1">
            {llmVerification.model && <div><span className="text-gray-500">Model:</span> {String(llmVerification.model)}</div>}
            {llmVerification.confidence != null && <div><span className="text-gray-500">Confidence:</span> {String(llmVerification.confidence)}</div>}
            {llmVerification.justification && <div><span className="text-gray-500">Justification:</span> {String(llmVerification.justification)}</div>}
          </div>
        </div>
      )}

      {/* Context summary / expand */}
      {!showFull && Object.keys(context).length > 0 && (
        <button
          onClick={() => setShowFull(true)}
          className="text-xs text-blue-600 underline"
        >
          Show full context
        </button>
      )}
      {showFull && (
        <div>
          <h4 className="text-sm font-semibold mb-2">Full Context</h4>
          <pre className="text-xs bg-white border rounded p-2 overflow-auto max-h-48">
            {JSON.stringify(context, null, 2)}
          </pre>
          <button onClick={() => setShowFull(false)} className="text-xs text-blue-600 underline mt-1">
            Hide
          </button>
        </div>
      )}

      {candidates.length === 0 && !llmVerification && (
        <p className="text-sm text-gray-500">No evidence data available for this flag.</p>
      )}
    </div>
  );
}

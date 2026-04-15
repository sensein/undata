"use client";

import { useState } from "react";

export interface EvidenceChainData {
  similarity_score: number;
  similarity_method: string;
  source_text: string;
  target_term_uri: string;
  target_term_label: string;
  target_term_definition?: string | null;
  uri_verified: boolean;
  reasoning: string;
}

interface EvidenceChainProps {
  evidence: EvidenceChainData;
  compact?: boolean;
}

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.8
      ? "bg-green-100 text-green-800"
      : score >= 0.6
        ? "bg-yellow-100 text-yellow-800"
        : "bg-red-100 text-red-800";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono ${color}`}>
      {pct}%
    </span>
  );
}

function UriBadge({ verified, uri }: { verified: boolean; uri: string }) {
  return (
    <a
      href={uri}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded ${
        verified
          ? "bg-blue-100 text-blue-800 hover:bg-blue-200"
          : "bg-gray-100 text-gray-500 hover:bg-gray-200"
      }`}
    >
      {verified ? "\u2713" : "?"} URI
    </a>
  );
}

export function EvidenceChain({ evidence, compact = false }: EvidenceChainProps) {
  const [expanded, setExpanded] = useState(false);

  if (compact) {
    return (
      <span className="inline-flex items-center gap-1.5">
        <ScoreBadge score={evidence.similarity_score} />
        <UriBadge verified={evidence.uri_verified} uri={evidence.target_term_uri} />
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-blue-600 underline"
        >
          {expanded ? "hide" : "why?"}
        </button>
        {expanded && (
          <span className="text-xs text-gray-600 ml-1">{evidence.reasoning}</span>
        )}
      </span>
    );
  }

  return (
    <div className="border rounded-lg p-3 bg-gray-50 space-y-2 text-sm">
      <div className="flex items-center gap-2 flex-wrap">
        <ScoreBadge score={evidence.similarity_score} />
        <span className="text-xs text-gray-500">({evidence.similarity_method})</span>
        <UriBadge verified={evidence.uri_verified} uri={evidence.target_term_uri} />
        <span className="font-medium">{evidence.target_term_label}</span>
      </div>

      {evidence.target_term_definition && (
        <p className="text-xs text-gray-600 italic">{evidence.target_term_definition}</p>
      )}

      <div className="text-xs text-gray-500">
        <span className="font-medium">Matched from:</span> {evidence.source_text}
      </div>

      <div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-blue-600 underline"
        >
          {expanded ? "Hide reasoning" : "Show reasoning"}
        </button>
        {expanded && (
          <p className="text-xs text-gray-700 mt-1 whitespace-pre-wrap">{evidence.reasoning}</p>
        )}
      </div>
    </div>
  );
}

interface EvidenceChainListProps {
  evidences: EvidenceChainData[];
}

export function EvidenceChainList({ evidences }: EvidenceChainListProps) {
  if (!evidences || evidences.length === 0) return null;
  return (
    <div className="space-y-2">
      {evidences.map((e, i) => (
        <EvidenceChain key={i} evidence={e} />
      ))}
    </div>
  );
}

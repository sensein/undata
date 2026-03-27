"use client";

import { useState } from "react";
import { useQuery } from "@apollo/client/react";
import { CURATION_QUEUE } from "@/graphql/queries";
import { StatusBadge } from "@/components/StatusBadge";
import { EvidencePanel } from "@/components/EvidencePanel";
import type { CurationFlagConnection, Edge, CurationFlagNode } from "@/graphql/types";

export default function CurationPage() {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, loading, error } = useQuery<{ curationQueue: CurationFlagConnection }>(
    CURATION_QUEUE,
    { variables: { first: 50 } },
  );

  const flags = data?.curationQueue?.edges ?? [];
  const totalCount = data?.curationQueue?.totalCount ?? 0;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Curation Queue</h1>
      <p className="text-sm text-gray-500 mb-6">{totalCount} pending flags</p>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 mb-6">
          <p className="text-red-800">Unable to load curation queue: {error.message}</p>
        </div>
      )}

      {loading && !data && (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-20 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      )}

      {!loading && !error && flags.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500 text-lg">No pending flags</p>
          <p className="text-gray-400 text-sm mt-1">All curation items have been resolved.</p>
        </div>
      )}

      <div className="space-y-3">
        {flags.map(({ node, cursor }: Edge<CurationFlagNode>) => {
          const isExpanded = expandedId === node.id;
          const ctx = (node.context ?? {}) as Record<string, unknown>;

          return (
            <div key={cursor} className="border rounded-lg overflow-hidden">
              {/* Collapsed header — click to expand */}
              <button
                className="w-full p-4 text-left flex items-center justify-between hover:bg-gray-50 transition-colors"
                onClick={() => setExpandedId(isExpanded ? null : node.id)}
              >
                <div className="flex items-center gap-3">
                  <StatusBadge status={node.status} />
                  <span className="px-2 py-0.5 bg-yellow-100 text-yellow-800 rounded text-xs font-medium">
                    {node.flagType.replace(/_/g, " ")}
                  </span>
                  <span className="font-mono text-sm">{node.entityRef}</span>
                  <span className="text-gray-400 text-xs">{node.entityType}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400">{node.createdAt}</span>
                  <span className="text-gray-400">{isExpanded ? "▲" : "▼"}</span>
                </div>
              </button>

              {/* Expanded evidence panel */}
              {isExpanded && (
                <div className="border-t p-4 bg-gray-50">
                  <EvidencePanel
                    context={ctx}
                    llmVerification={ctx.llm_verification as Record<string, unknown> | undefined}
                  />

                  {/* Resolution context */}
                  {node.resolvedBy && (
                    <div className="mt-4 text-sm text-gray-600">
                      <strong>Resolved by:</strong> {node.resolvedBy}
                      {node.resolutionNote && <span> — {node.resolutionNote}</span>}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

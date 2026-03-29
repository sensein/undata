"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@apollo/client/react";
import { CURATION_QUEUE, RESOLVE_FLAG } from "@/graphql/queries";
import { StatusBadge } from "@/components/StatusBadge";
import { EvidencePanel } from "@/components/EvidencePanel";
import { useAuth } from "@/components/AuthProvider";
import type { CurationFlagConnection, Edge, CurationFlagNode } from "@/graphql/types";

export default function CurationPage() {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [resolveNote, setResolveNote] = useState("");
  const { user, hasRole } = useAuth();
  const canResolve = hasRole("curator");

  const { data, loading, error, refetch } = useQuery<{ curationQueue: CurationFlagConnection }>(
    CURATION_QUEUE,
    { variables: { status: "PENDING", first: 50 } },
  );

  const [resolveFlag, { loading: resolving }] = useMutation(RESOLVE_FLAG, {
    onCompleted: () => {
      setExpandedId(null);
      setResolveNote("");
      refetch();
    },
  });

  const handleResolve = (flagId: string, action: string) => {
    resolveFlag({
      variables: {
        input: {
          flagId,
          action,
          resolvedBy: user?.name ?? "unknown",
          note: resolveNote || undefined,
        },
      },
    });
  };

  const flags = data?.curationQueue?.edges ?? [];
  const totalCount = data?.curationQueue?.totalCount ?? 0;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Curation Queue</h1>
      <p className="text-sm text-gray-500 mb-6">{totalCount} pending flags</p>

      {!canResolve && user && (
        <div className="bg-blue-50 border border-blue-200 rounded p-3 mb-6 text-sm text-blue-700">
          You have viewer access. Curator role required to resolve flags.
        </div>
      )}

      {!user && (
        <div className="bg-gray-50 border border-gray-200 rounded p-3 mb-6 text-sm text-gray-600">
          Sign in with curator role to resolve flags.
        </div>
      )}

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
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const ctx = (node.context ?? {}) as Record<string, any>;

          return (
            <div key={cursor} className="border rounded-lg overflow-hidden">
              {/* Header */}
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

              {/* Expanded panel */}
              {isExpanded && (
                <div className="border-t p-4 bg-gray-50 space-y-4">
                  <EvidencePanel
                    context={ctx}
                    llmVerification={ctx.llm_verification as Record<string, unknown> | undefined}
                  />

                  {/* Resolve actions */}
                  {canResolve && node.status.toLowerCase() === "pending" && (
                    <div className="border-t pt-4 mt-4">
                      <h4 className="text-sm font-semibold mb-2">Resolve this flag</h4>
                      <textarea
                        className="w-full border rounded p-2 text-sm mb-3"
                        rows={2}
                        placeholder="Resolution note (optional)..."
                        value={resolveNote}
                        onChange={(e) => setResolveNote(e.target.value)}
                      />
                      <div className="flex gap-2">
                        <button
                          className="px-4 py-2 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
                          onClick={() => handleResolve(node.id, "APPROVED")}
                          disabled={resolving}
                        >
                          ✓ Approve
                        </button>
                        <button
                          className="px-4 py-2 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
                          onClick={() => handleResolve(node.id, "REJECTED")}
                          disabled={resolving}
                        >
                          ✗ Reject
                        </button>
                        <button
                          className="px-4 py-2 bg-gray-500 text-white rounded text-sm hover:bg-gray-600 disabled:opacity-50"
                          onClick={() => handleResolve(node.id, "DEFERRED")}
                          disabled={resolving}
                        >
                          — Defer
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Quick actions */}
                  <div className="border-t pt-3 mt-3 flex gap-2">
                    <a
                      href={`/curation/chat?entity=${node.entityRef}`}
                      className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded text-xs hover:bg-blue-100"
                    >
                      Open in Chat →
                    </a>
                  </div>

                  {/* Already resolved */}
                  {node.resolvedBy && (
                    <div className="text-sm text-gray-600 border-t pt-3">
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

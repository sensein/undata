"use client";

import { useQuery } from "@apollo/client/react";
import { CURATION_QUEUE } from "@/graphql/queries";
import type { CurationFlagConnection, Edge, CurationFlagNode } from "@/graphql/types";

export default function CurationPage() {
  const { data, loading, error } = useQuery<{ curationQueue: CurationFlagConnection }>(
    CURATION_QUEUE,
    { variables: { first: 50 } },
  );

  const flags = data?.curationQueue?.edges ?? [];
  const totalCount = data?.curationQueue?.totalCount ?? 0;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Curation Queue</h1>
      <p className="text-gray-500 mb-6">{totalCount} pending flags</p>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 mb-6">
          <p className="text-red-800">Unable to load curation queue: {error.message}</p>
        </div>
      )}

      {loading && !data && (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />
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
        {flags.map(({ node, cursor }: Edge<CurationFlagNode>) => (
          <div key={cursor} className="border rounded p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-xs font-medium">
                  {node.flagType.replace(/_/g, " ")}
                </span>
                <span className="font-mono text-sm">{node.entityRef}</span>
                <span className="text-gray-400 text-xs">{node.entityType}</span>
              </div>
              <span className="text-xs text-gray-400">{node.createdAt}</span>
            </div>
            {node.context && typeof node.context === "object" && (
              <div className="text-sm text-gray-600">
                {(node.context as Record<string, unknown>).reason
                  ? String((node.context as Record<string, unknown>).reason)
                  : JSON.stringify(node.context).slice(0, 100)}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

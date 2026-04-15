"use client";

import { useQuery } from "@apollo/client/react";
import { RUN_SUMMARIES } from "@/graphql/queries";
import type { RunSummaryConnection, Edge, RunSummaryNode } from "@/graphql/types";

export default function RunsPage() {
  const { data, loading, error } = useQuery<{ runSummaries: RunSummaryConnection }>(
    RUN_SUMMARIES,
    { variables: { first: 20 } },
  );

  const runs = data?.runSummaries?.edges ?? [];
  const totalCount = data?.runSummaries?.totalCount ?? 0;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Pipeline Runs</h1>
      <p className="text-gray-500 mb-6">{totalCount} runs</p>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 mb-6">
          <p className="text-red-800">Unable to load runs: {error.message}</p>
        </div>
      )}

      {loading && !data && (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-20 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      )}

      {!loading && !error && runs.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500 text-lg">No pipeline runs yet</p>
          <p className="text-gray-400 text-sm mt-1">
            Run the pipeline via CLI or GraphQL mutation to see results here.
          </p>
        </div>
      )}

      <div className="space-y-3">
        {runs.map(({ node, cursor }: Edge<RunSummaryNode>) => (
          <div key={cursor} className="border rounded p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs font-medium">
                  {node.source}
                </span>
                <span className="font-mono text-sm">{node.runId}</span>
              </div>
              <span className="text-xs text-gray-400">{node.startedAt}</span>
            </div>
            {node.entityCounts && typeof node.entityCounts === "object" && (
              <div className="text-sm text-gray-600">
                {Object.entries(node.entityCounts as Record<string, unknown>)
                  .map(([k, v]) =>
                    typeof v === "object" && v !== null
                      ? `${k}: ${JSON.stringify(v)}`
                      : `${k}: ${v}`,
                  )
                  .join(" · ")}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

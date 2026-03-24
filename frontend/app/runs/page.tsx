"use client";

import { useQuery } from "@apollo/client/react";
import { RUN_SUMMARIES } from "@/graphql/queries";
import type { RunSummaryNode } from "@/graphql/types";

export default function RunsPage() {
  const { data, loading, error } = useQuery<{
    runSummaries: import("@/graphql/types").RunSummaryNode[];
  }>(RUN_SUMMARIES);
  const runs = data?.runSummaries ?? [];

  return (
    <div className="max-w-7xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Pipeline Runs</h1>

      {loading && <p className="text-gray-500">Loading...</p>}
      {error && <p className="text-red-500">Error: {error.message}</p>}

      <div className="space-y-4">
        {runs.map((run: RunSummaryNode) => (
          <div key={run.runId} className="border rounded p-4">
            <div className="flex justify-between items-start">
              <div>
                <span className="font-mono text-sm">{run.runId}</span>
                <span className="ml-3 px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">
                  {run.source}
                </span>
              </div>
              <span className="text-xs text-gray-500">{run.startedAt}</span>
            </div>

            {run.entityCounts && (
              <div className="mt-3 grid grid-cols-4 gap-4 text-sm">
                {Object.entries(run.entityCounts).map(
                  ([stage, counts]) => (
                    <div key={stage}>
                      <div className="text-xs text-gray-500 uppercase">{stage}</div>
                      {typeof counts === "object" ? (
                        <div>
                          {Object.entries(counts).map(([k, v]) => (
                            <div key={k} className="text-xs">
                              {k}: {String(v)}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div>{String(counts)}</div>
                      )}
                    </div>
                  )
                )}
              </div>
            )}

            {run.timing && (
              <div className="mt-2 text-xs text-gray-500">
                {Object.entries(run.timing as Record<string, number>)
                  .map(([k, v]) => `${k}: ${v.toFixed(1)}s`)
                  .join(" · ")}
              </div>
            )}
          </div>
        ))}

        {runs.length === 0 && !loading && (
          <p className="text-gray-500">No pipeline runs found.</p>
        )}
      </div>
    </div>
  );
}

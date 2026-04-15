"use client";

import { useQuery } from "@apollo/client/react";
import { INGESTION_QUEUE } from "@/graphql/queries";

interface IngestionJobNode {
  id: string;
  repositoryUrl: string;
  adapterType: string;
  status: string;
  autoApproved: boolean;
  entityCounts?: Record<string, number>;
  errorMessage?: string;
  approvedBy?: string;
  startedAt?: string;
  completedAt?: string;
  createdAt: string;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  approved: "bg-blue-100 text-blue-800",
  running: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

export default function IngestionQueuePage() {
  const { data, loading, error } = useQuery<{ ingestionQueue: IngestionJobNode[] }>(INGESTION_QUEUE);

  const jobs = data?.ingestionQueue ?? [];

  return (
    <div>
      <h1 className="text-xl font-bold mb-4">Ingestion Queue</h1>
      <p className="text-sm text-gray-500 mb-4">
        Dataset ingestion jobs — auto-discovered from approved sources or manually queued by curators.
      </p>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-3 mb-4 text-sm text-red-800">
          {error.message}
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="border rounded overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b">
                <th className="text-left px-3 py-2 font-medium">Status</th>
                <th className="text-left px-3 py-2 font-medium">Repository</th>
                <th className="text-left px-3 py-2 font-medium">Adapter</th>
                <th className="text-left px-3 py-2 font-medium">Entities</th>
                <th className="text-left px-3 py-2 font-medium">Queued</th>
              </tr>
            </thead>
            <tbody>
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-gray-500">
                    No ingestion jobs yet. Jobs appear when the discovery service finds new datasets.
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.id} className="border-b hover:bg-gray-50">
                    <td className="px-3 py-2">
                      <span className={`px-1.5 py-0.5 rounded text-xs ${STATUS_COLORS[job.status] ?? "bg-gray-100"}`}>
                        {job.status}
                      </span>
                      {job.autoApproved && (
                        <span className="ml-1 text-[10px] text-gray-400">auto</span>
                      )}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs truncate max-w-xs" title={job.repositoryUrl}>
                      {job.repositoryUrl}
                    </td>
                    <td className="px-3 py-2">
                      <span className="px-1.5 py-0.5 bg-gray-100 rounded text-xs">{job.adapterType}</span>
                    </td>
                    <td className="px-3 py-2 text-xs">
                      {job.entityCounts ? (
                        Object.entries(job.entityCounts).map(([k, v]) => (
                          <span key={k} className="mr-2">{k}: {v}</span>
                        ))
                      ) : "—"}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-500">
                      {new Date(job.createdAt).toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

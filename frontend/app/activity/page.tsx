"use client";

import { useMemo } from "react";
import { useQuery } from "@apollo/client/react";
import { CURATION_QUEUE } from "@/graphql/queries";
import { ActivityTimeline } from "@/components/ActivityTimeline";
import type { CurationFlagConnection, Edge, CurationFlagNode } from "@/graphql/types";

export default function ActivityPage() {
  // Source activity from curation flags (sorted by created_at)
  // Future: merge with contributions when that data is available
  const { data, loading, error } = useQuery<{ curationQueue: CurationFlagConnection }>(
    CURATION_QUEUE,
    { variables: { first: 50, status: null } }, // all statuses
  );

  const events = useMemo(() => {
    const flags = data?.curationQueue?.edges ?? [];
    return flags.map(({ node }: Edge<CurationFlagNode>) => ({
      type: node.status === "approved" || node.status === "rejected" ? "flag_resolved" : "flag_created",
      entityRef: node.entityRef,
      entityType: node.entityType,
      timestamp: node.createdAt,
      description: `${node.flagType.replace(/_/g, " ")} — ${node.entityRef}`,
      status: node.status,
    }));
  }, [data]);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Activity</h1>
      <p className="text-sm text-gray-500 mb-6">Recent platform activity</p>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 mb-6">
          <p className="text-red-800">Unable to load activity: {error.message}</p>
        </div>
      )}

      {loading && !data && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      )}

      <ActivityTimeline events={events} />
    </div>
  );
}

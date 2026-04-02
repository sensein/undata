"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation } from "@apollo/client/react";
import { createColumnHelper } from "@tanstack/react-table";
import { CURATION_QUEUE, RESOLVE_FLAG } from "@/graphql/queries";
import { EntityDataGrid } from "@/components/EntityDataGrid";
import { EntityTag } from "@/components/EntityTag";
import { StatusBadge } from "@/components/StatusBadge";
import { useAuth } from "@/components/AuthProvider";
import type { CurationFlagConnection, CurationFlagNode, Edge } from "@/graphql/types";

const ENTITY_TYPE_TO_PATH: Record<string, string> = {
  element: "elements",
  schema: "schemas",
  value: "values",
  valueset: "valuesets",
  transform: "transforms",
};

function relativeTime(dateStr: string): string {
  const now = new Date();
  const then = new Date(dateStr);
  const diffMs = now.getTime() - then.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 30) return `${diffDay}d ago`;
  const diffMon = Math.floor(diffDay / 30);
  return `${diffMon}mo ago`;
}

const columnHelper = createColumnHelper<CurationFlagNode>();

export default function CurationPage() {
  const [flagTypeFilter, setFlagTypeFilter] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState<string | undefined>("PENDING");
  const [resolveNote, setResolveNote] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const { user, hasRole } = useAuth();
  const canResolve = hasRole("curator");

  const { data, loading, error, refetch, fetchMore } = useQuery<{ curationQueue: CurationFlagConnection }>(
    CURATION_QUEUE,
    {
      variables: {
        flagType: flagTypeFilter || undefined,
        status: statusFilter || undefined,
        first: 50,
      },
    },
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

  const flags = useMemo(
    () => (data?.curationQueue?.edges ?? []).map((e: Edge<CurationFlagNode>) => e.node),
    [data],
  );
  const totalCount = data?.curationQueue?.totalCount ?? 0;
  const pageInfo = data?.curationQueue?.pageInfo;

  const columns = useMemo(
    () => [
      columnHelper.accessor("status", {
        header: "Status",
        cell: (info) => <StatusBadge status={info.getValue()} />,
        enableColumnFilter: false,
      }),
      columnHelper.accessor("flagType", {
        header: "Flag Type",
        cell: (info) => (
          <span className="px-2 py-0.5 bg-yellow-100 text-yellow-800 rounded text-xs font-medium whitespace-nowrap">
            {info.getValue().replace(/_/g, " ")}
          </span>
        ),
        enableColumnFilter: false,
      }),
      columnHelper.accessor("entityRef", {
        header: "Entity",
        cell: (info) => {
          const entityType = ENTITY_TYPE_TO_PATH[info.row.original.entityType.toLowerCase()] ?? "elements";
          const ref = info.getValue();
          return (
            <EntityTag
              entityType={entityType}
              sha256={ref}
              label={ref.slice(0, 12)}
              showPopover={true}
            />
          );
        },
        enableColumnFilter: false,
      }),
      columnHelper.display({
        id: "reason",
        header: "Reason",
        cell: (info) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const ctx = (info.row.original.context ?? {}) as Record<string, any>;
          const reason = ctx.reason ?? ctx.message ?? "";
          const truncated = reason.length > 80 ? reason.slice(0, 80) + "..." : reason;
          return (
            <span className="text-gray-600 text-sm" title={reason}>
              {truncated || "\u2014"}
            </span>
          );
        },
        enableSorting: false,
        enableColumnFilter: false,
      }),
      columnHelper.accessor("createdAt", {
        header: "Created",
        cell: (info) => (
          <span className="text-gray-500 text-xs whitespace-nowrap" title={info.getValue()}>
            {relativeTime(info.getValue())}
          </span>
        ),
        enableColumnFilter: false,
      }),
      columnHelper.display({
        id: "actions",
        header: "",
        cell: (info) => {
          const node = info.row.original;
          const isExpanded = expandedId === node.id;
          return (
            <button
              className="text-xs text-blue-600 hover:text-blue-800"
              onClick={() => setExpandedId(isExpanded ? null : node.id)}
            >
              {isExpanded ? "Close" : "Actions"}
            </button>
          );
        },
        enableSorting: false,
        enableColumnFilter: false,
      }),
    ],
    [expandedId],
  );

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Curation Queue</h1>
      <p className="text-sm text-gray-500 mb-6">{totalCount} flags</p>

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

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <select
          className="border rounded px-3 py-2 text-sm"
          value={flagTypeFilter ?? ""}
          onChange={(e) => setFlagTypeFilter(e.target.value || undefined)}
        >
          <option value="">All flag types</option>
          <option value="LOW_CONFIDENCE">Low confidence</option>
          <option value="MISSING_ANNOTATION">Missing annotation</option>
          <option value="AMBIGUOUS_MAPPING">Ambiguous mapping</option>
          <option value="SCHEMA_CONFLICT">Schema conflict</option>
          <option value="DUPLICATE_CANDIDATE">Duplicate candidate</option>
        </select>

        <select
          className="border rounded px-3 py-2 text-sm"
          value={statusFilter ?? ""}
          onChange={(e) => setStatusFilter(e.target.value || undefined)}
        >
          <option value="">All statuses</option>
          <option value="PENDING">Pending</option>
          <option value="APPROVED">Approved</option>
          <option value="REJECTED">Rejected</option>
          <option value="DEFERRED">Deferred</option>
        </select>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 mb-6">
          <p className="text-red-800">Unable to load curation queue: {error.message}</p>
        </div>
      )}

      {/* Data grid */}
      <EntityDataGrid
        columns={columns}
        data={flags}
        isLoading={loading}
        totalCount={totalCount}
        hasNextPage={pageInfo?.hasNextPage}
        onLoadMore={() =>
          fetchMore({ variables: { after: pageInfo?.endCursor } })
        }
      />

      {/* Resolve panel (shown below table when a row's "Actions" is clicked) */}
      {expandedId && canResolve && (() => {
        const node = flags.find((f) => f.id === expandedId);
        if (!node || node.status.toLowerCase() !== "pending") return null;
        return (
          <div className="mt-4 border rounded-lg p-4 bg-gray-50">
            <div className="flex items-center gap-3 mb-3">
              <h4 className="text-sm font-semibold">Resolve flag for</h4>
              <EntityTag
                entityType={ENTITY_TYPE_TO_PATH[node.entityType.toLowerCase()] ?? "elements"}
                sha256={node.entityRef}
                label={node.entityRef.slice(0, 16)}
              />
              <StatusBadge status={node.status} />
              <a
                href={`/${ENTITY_TYPE_TO_PATH[node.entityType.toLowerCase()] ?? "elements"}/${node.entityRef}`}
                className="text-xs text-blue-600 hover:underline ml-auto"
                target="_blank"
                rel="noopener noreferrer"
              >
                View full details ↗
              </a>
            </div>
            {/* Flag context */}
            {node.context && (
              <div className="bg-white border rounded p-2 mb-3 text-xs">
                <span className="text-gray-500 font-medium">Flag context: </span>
                <span className="text-gray-700">
                  {String(
                    (node.context as Record<string, unknown>)?.reason ??
                    (node.context as Record<string, unknown>)?.message ??
                    JSON.stringify(node.context).slice(0, 200)
                  )}
                </span>
              </div>
            )}
            {node.resolvedBy && (
              <div className="text-sm text-gray-600 mb-3">
                <strong>Resolved by:</strong> {node.resolvedBy}
                {node.resolutionNote && <span> &mdash; {node.resolutionNote}</span>}
              </div>
            )}
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
                Approve
              </button>
              <button
                className="px-4 py-2 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50"
                onClick={() => handleResolve(node.id, "REJECTED")}
                disabled={resolving}
              >
                Reject
              </button>
              <button
                className="px-4 py-2 bg-gray-500 text-white rounded text-sm hover:bg-gray-600 disabled:opacity-50"
                onClick={() => handleResolve(node.id, "DEFERRED")}
                disabled={resolving}
              >
                Defer
              </button>
              <button
                className="px-4 py-2 border text-gray-600 rounded text-sm hover:bg-gray-100"
                onClick={() => setExpandedId(null)}
              >
                Cancel
              </button>
            </div>
          </div>
        );
      })()}
    </div>
  );
}

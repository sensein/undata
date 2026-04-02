"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@apollo/client/react";
import { createColumnHelper } from "@tanstack/react-table";
import { BROWSE_VALUESETS } from "@/graphql/queries";
import { EntityDataGrid } from "@/components/EntityDataGrid";
import { EntityTag } from "@/components/EntityTag";
import { SourceBadge } from "@/components/SourceBadge";

interface ValueSetNode {
  sha256: string;
  name?: string;
  members: string[];
  description?: string;
  provenance: { source: string; name: string }[];
}

interface VSConnection {
  edges: { node: ValueSetNode; cursor: string }[];
  pageInfo: { hasNextPage: boolean; endCursor?: string };
  totalCount: number;
}

const columnHelper = createColumnHelper<ValueSetNode>();

export default function ValueSetsPage() {
  const [source, setSource] = useState<string | undefined>();
  const [searchText, setSearchText] = useState("");

  const { data, loading, error, fetchMore } = useQuery<{ browseValuesets: VSConnection }>(
    BROWSE_VALUESETS,
    { variables: { source, searchText: searchText || undefined, first: 50 } },
  );

  const valuesets = useMemo(
    () => (data?.browseValuesets?.edges ?? []).map((e) => e.node),
    [data],
  );
  const pageInfo = data?.browseValuesets?.pageInfo;
  const totalCount = data?.browseValuesets?.totalCount ?? 0;

  const columns = useMemo(
    () => [
      columnHelper.accessor("sha256", {
        header: "Name",
        cell: (info) => (
          <EntityTag
            entityType="valuesets"
            sha256={info.getValue()}
            label={info.row.original.name ?? info.getValue().slice(0, 12)}
          />
        ),
        enableColumnFilter: false,
      }),
      columnHelper.display({
        id: "source",
        header: "Source",
        cell: (info) => {
          const prov = info.row.original.provenance?.[0];
          return prov?.source ? <SourceBadge source={prov.source} /> : "—";
        },
        enableSorting: false,
        enableColumnFilter: false,
      }),
      columnHelper.display({
        id: "members",
        header: "Members",
        cell: (info) => {
          const count = info.row.original.members?.length ?? 0;
          return count > 0 ? (
            <a
              href={`/valuesets/${info.row.original.sha256}`}
              className="text-blue-600 hover:underline text-sm"
            >
              {count} members
            </a>
          ) : "—";
        },
        enableSorting: false,
        enableColumnFilter: false,
      }),
      columnHelper.accessor("description", {
        header: "Description",
        cell: (info) => (
          <span className="text-gray-600 text-sm truncate block max-w-xs">{info.getValue() ?? "—"}</span>
        ),
        enableSorting: false,
      }),
    ],
    [],
  );

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Value Sets</h1>
      <div className="flex flex-wrap gap-3 mb-6">
        <select
          className="border rounded px-3 py-2 text-sm"
          value={source ?? ""}
          onChange={(e) => setSource(e.target.value || undefined)}
        >
          <option value="">All sources</option>
          <option value="bids">BIDS</option>
          <option value="dandi">DANDI</option>
          <option value="nwb">NWB</option>
          <option value="openminds">openMINDS</option>
          <option value="aind">AIND</option>
        </select>
        <input
          type="text"
          className="border rounded px-3 py-2 text-sm w-64"
          placeholder="Search value sets..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
      </div>
      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 mb-6">
          <p className="text-red-800">Unable to load value sets: {error.message}</p>
        </div>
      )}
      <EntityDataGrid
        columns={columns}
        data={valuesets}
        isLoading={loading}
        totalCount={totalCount}
        hasNextPage={pageInfo?.hasNextPage}
        onLoadMore={() => fetchMore({ variables: { after: pageInfo?.endCursor } })}
      />
    </div>
  );
}

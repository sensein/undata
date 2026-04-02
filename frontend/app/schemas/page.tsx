"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@apollo/client/react";
import { createColumnHelper } from "@tanstack/react-table";
import { BROWSE_SCHEMAS } from "@/graphql/queries";
import { EntityDataGrid } from "@/components/EntityDataGrid";
import { EntityTag } from "@/components/EntityTag";
import { SourceBadge } from "@/components/SourceBadge";
import type { SchemaConnection, SchemaNode, Edge } from "@/graphql/types";

const columnHelper = createColumnHelper<SchemaNode>();

export default function SchemasPage() {
  const [source, setSource] = useState<string | undefined>();
  const [searchText, setSearchText] = useState("");

  const { data, loading, error, fetchMore } = useQuery<{ browseSchemas: SchemaConnection }>(
    BROWSE_SCHEMAS,
    { variables: { source, searchText: searchText || undefined, first: 50 } },
  );

  const schemas = useMemo(
    () => (data?.browseSchemas?.edges ?? []).map((e: Edge<SchemaNode>) => e.node),
    [data],
  );
  const pageInfo = data?.browseSchemas?.pageInfo;
  const totalCount = data?.browseSchemas?.totalCount ?? 0;

  const columns = useMemo(
    () => [
      columnHelper.accessor("sha256", {
        header: "Name",
        cell: (info) => {
          const prov = info.row.original.provenance?.[0];
          return (
            <EntityTag
              entityType="schemas"
              sha256={info.getValue()}
              label={prov?.name ?? info.getValue().slice(0, 12)}
            />
          );
        },
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
        id: "properties",
        header: "Properties",
        cell: (info) => {
          const count = info.row.original.properties?.length ?? 0;
          return count > 0 ? (
            <a href={`/schemas/${info.row.original.sha256}`} className="text-blue-600 hover:underline text-sm">
              {count} properties
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
      <h1 className="text-2xl font-bold mb-6">Schemas</h1>
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
          placeholder="Search schemas..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
      </div>
      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 mb-6">
          <p className="text-red-800">Unable to load schemas: {error.message}</p>
        </div>
      )}
      <EntityDataGrid
        columns={columns}
        data={schemas}
        isLoading={loading}
        totalCount={totalCount}
        hasNextPage={pageInfo?.hasNextPage}
        onLoadMore={() => fetchMore({ variables: { after: pageInfo?.endCursor } })}
      />
    </div>
  );
}

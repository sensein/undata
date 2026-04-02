"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@apollo/client/react";
import { createColumnHelper } from "@tanstack/react-table";
import { BROWSE_VALUES } from "@/graphql/queries";
import { EntityDataGrid } from "@/components/EntityDataGrid";
import { EntityTag } from "@/components/EntityTag";
import { SourceBadge } from "@/components/SourceBadge";
import type { ValueConnection, ValueNode, Edge, OntologyAnnotation } from "@/graphql/types";

const columnHelper = createColumnHelper<ValueNode>();

// Map TanStack column IDs to backend sort field names
const SORT_FIELD_MAP: Record<string, string> = {
  sha256: "name",
  valueType: "valueType",
  description: "description",
};

export default function ValuesPage() {
  const [source, setSource] = useState<string | undefined>();
  const [searchText, setSearchText] = useState("");
  const [sortBy, setSortBy] = useState<string | undefined>();
  const [sortOrder, setSortOrder] = useState<string | undefined>();

  const { data, loading, error, fetchMore } = useQuery<{ browseValues: ValueConnection }>(
    BROWSE_VALUES,
    { variables: { source, searchText: searchText || undefined, sortBy, sortOrder, first: 50 } },
  );

  const values = useMemo(
    () => (data?.browseValues?.edges ?? []).map((e: Edge<ValueNode>) => e.node),
    [data],
  );
  const pageInfo = data?.browseValues?.pageInfo;
  const totalCount = data?.browseValues?.totalCount ?? 0;

  const columns = useMemo(
    () => [
      columnHelper.accessor("sha256", {
        header: "Label",
        cell: (info) => (
          <EntityTag
            entityType="values"
            sha256={info.getValue()}
            label={info.row.original.label ?? info.getValue().slice(0, 12)}
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
      columnHelper.accessor("valueType", {
        header: "Type",
        cell: (info) => info.getValue() ?? "—",
      }),
      columnHelper.display({
        id: "ontology",
        header: "Ontology",
        cell: (info) => {
          const primary = info.row.original.ontologyAnnotations?.find((a: OntologyAnnotation) => a.primary);
          return primary ? (
            <span className="text-green-700 text-sm">{primary.termLabel}</span>
          ) : (
            <span className="text-gray-400">—</span>
          );
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
      <h1 className="text-2xl font-bold mb-6">Values</h1>
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
          placeholder="Search values..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
      </div>
      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 mb-6">
          <p className="text-red-800">Unable to load values: {error.message}</p>
        </div>
      )}
      <EntityDataGrid
        columns={columns}
        data={values}
        isLoading={loading}
        totalCount={totalCount}
        hasNextPage={pageInfo?.hasNextPage}
        onLoadMore={() => fetchMore({ variables: { after: pageInfo?.endCursor } })}
        onSortChange={(columnId, direction) => {
          if (direction === false) {
            setSortBy(undefined);
            setSortOrder(undefined);
          } else {
            setSortBy(SORT_FIELD_MAP[columnId] || columnId);
            setSortOrder(direction);
          }
        }}
      />
    </div>
  );
}

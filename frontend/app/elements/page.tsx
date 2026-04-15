"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@apollo/client/react";
import { createColumnHelper } from "@tanstack/react-table";
import { BROWSE_ELEMENTS } from "@/graphql/queries";
import { EntityDataGrid } from "@/components/EntityDataGrid";
import { EntityTag } from "@/components/EntityTag";
import { SourceBadge } from "@/components/SourceBadge";
import type { ElementConnection, ElementNode, Edge, OntologyAnnotation } from "@/graphql/types";

const columnHelper = createColumnHelper<ElementNode>();

// Map TanStack column IDs to backend sort field names
const SORT_FIELD_MAP: Record<string, string> = {
  sha256: "name",
  dataType: "dataType",
  unit: "unit",
  description: "description",
};

export default function ElementsPage() {
  const [source, setSource] = useState<string | undefined>();
  const [dataType, setDataType] = useState<string | undefined>();
  const [searchText, setSearchText] = useState("");
  const [sortBy, setSortBy] = useState<string | undefined>();
  const [sortOrder, setSortOrder] = useState<string | undefined>();

  const { data, loading, error, fetchMore } = useQuery<{ browseElements: ElementConnection }>(
    BROWSE_ELEMENTS,
    {
      variables: {
        source,
        dataType: dataType?.toUpperCase(),
        searchText: searchText || undefined,
        sortBy,
        sortOrder,
        first: 50,
      },
    },
  );

  const elements = useMemo(
    () => (data?.browseElements?.edges ?? []).map((e: Edge<ElementNode>) => e.node),
    [data],
  );
  const pageInfo = data?.browseElements?.pageInfo;
  const totalCount = data?.browseElements?.totalCount ?? 0;

  const columns = useMemo(
    () => [
      columnHelper.accessor("sha256", {
        header: "Name",
        cell: (info) => {
          const prov = info.row.original.provenance?.[0];
          const name = prov?.name ?? info.row.original.fileName ?? info.getValue().slice(0, 12);
          // Show class prefix for disambiguation when name is generic
          const className = prov?.className;
          const label = className && className !== name ? `${name}::${className}` : name;
          return (
            <EntityTag
              entityType="elements"
              sha256={info.getValue()}
              label={label}
            />
          );
        },
        sortingFn: (rowA, rowB) => {
          const nameA = (rowA.original.provenance?.[0]?.name ?? rowA.original.fileName ?? "").toLowerCase();
          const nameB = (rowB.original.provenance?.[0]?.name ?? rowB.original.fileName ?? "").toLowerCase();
          return nameA.localeCompare(nameB);
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
      columnHelper.accessor("dataType", {
        header: "Type",
        cell: (info) => <span className="font-mono text-sm">{info.getValue() ?? "—"}</span>,
      }),
      columnHelper.accessor("unit", {
        header: "Unit",
        cell: (info) => info.getValue() ?? "—",
      }),
      columnHelper.display({
        id: "annotations",
        header: "Ontology",
        cell: (info) => {
          const anns = info.row.original.ontologyAnnotations ?? [];
          const primary = anns.find((a: OntologyAnnotation) => a.primary);
          if (!primary) return <span className="text-gray-400">—</span>;
          return (
            <a
              href={`/elements/${info.row.original.sha256}#annotations`}
              className="text-green-700 hover:underline text-sm"
            >
              {primary.termLabel} ({primary.score?.toFixed(2)})
            </a>
          );
        },
        enableSorting: false,
        enableColumnFilter: false,
      }),
      columnHelper.accessor("description", {
        header: "Description",
        cell: (info) => (
          <span className="text-gray-600 text-sm truncate block max-w-xs">
            {info.getValue() ?? info.row.original.provenance?.[0]?.description ?? "—"}
          </span>
        ),
        enableSorting: false,
      }),
    ],
    [],
  );

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Data Elements</h1>

      {/* Filters */}
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
          <option value="reproschema">ReproSchema</option>
          <option value="nda">NDA</option>
          <option value="openneuro">OpenNeuro</option>
        </select>

        <select
          className="border rounded px-3 py-2 text-sm"
          value={dataType ?? ""}
          onChange={(e) => setDataType(e.target.value || undefined)}
        >
          <option value="">All types</option>
          <option value="string">string</option>
          <option value="integer">integer</option>
          <option value="float">float</option>
          <option value="boolean">boolean</option>
          <option value="array">array</option>
          <option value="object">object</option>
        </select>

        <input
          type="text"
          className="border rounded px-3 py-2 text-sm w-64"
          placeholder="Search elements..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 mb-6">
          <p className="text-red-800">Unable to load elements: {error.message}</p>
        </div>
      )}

      {/* Data grid */}
      <EntityDataGrid
        columns={columns}
        data={elements}
        isLoading={loading}
        totalCount={totalCount}
        hasNextPage={pageInfo?.hasNextPage}
        onLoadMore={() =>
          fetchMore({ variables: { after: pageInfo?.endCursor } })
        }
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

"use client";

import { useQuery } from "@apollo/client/react";
import Link from "next/link";
import { useState } from "react";
import { BROWSE_ELEMENTS } from "@/graphql/queries";
import type { ElementConnection, Edge, ElementNode, OntologyAnnotation } from "@/graphql/types";

export default function ElementsPage() {
  const [source, setSource] = useState<string | undefined>();
  const [dataType, setDataType] = useState<string | undefined>();
  const [searchText, setSearchText] = useState<string>("");

  const { data, loading, error, fetchMore, refetch } = useQuery<{
    browseElements: ElementConnection;
  }>(BROWSE_ELEMENTS, {
    variables: {
      source,
      dataType: dataType?.toUpperCase(),
      searchText: searchText || undefined,
      first: 50,
    },
  });

  const elements = data?.browseElements?.edges ?? [];
  const pageInfo = data?.browseElements?.pageInfo;
  const totalCount = data?.browseElements?.totalCount ?? 0;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Data Elements</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-6">
        <select
          className="border rounded px-3 py-2"
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

        <select
          className="border rounded px-3 py-2"
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
          className="border rounded px-3 py-2 w-64"
          placeholder="Search elements..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
        />

        <span className="text-gray-500 self-center">{totalCount} elements</span>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 mb-6">
          <p className="text-red-800 font-medium">Unable to load elements</p>
          <p className="text-red-600 text-sm mt-1">{error.message}</p>
          <button
            className="mt-2 text-sm text-red-700 underline"
            onClick={() => refetch()}
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading state */}
      {loading && !data && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && elements.length === 0 && (
        <p className="text-gray-500 text-center py-12">
          No elements found. Try adjusting your filters.
        </p>
      )}

      {/* Data table */}
      {elements.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-gray-100 border-b">
                <th className="text-left p-3">Name</th>
                <th className="text-left p-3">Source</th>
                <th className="text-left p-3">Type</th>
                <th className="text-left p-3">Unit</th>
                <th className="text-left p-3">Ontology</th>
                <th className="text-left p-3">Description</th>
              </tr>
            </thead>
            <tbody>
              {elements.map(({ node, cursor }: Edge<ElementNode>) => {
                const prov = node.provenance?.[0];
                const primaryAnn = node.ontologyAnnotations?.find(
                  (a: OntologyAnnotation) => a.primary,
                );
                return (
                  <tr key={cursor} className="border-b hover:bg-gray-50">
                    <td className="p-3 font-mono text-sm">
                      <Link
                        href={`/elements/${node.sha256}`}
                        className="text-blue-600 hover:underline"
                      >
                        {prov?.name ?? node.fileName ?? node.sha256.slice(0, 12)}
                      </Link>
                    </td>
                    <td className="p-3">
                      <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">
                        {prov?.source}
                      </span>
                    </td>
                    <td className="p-3 text-sm">{node.dataType}</td>
                    <td className="p-3 text-sm">{node.unit ?? "—"}</td>
                    <td className="p-3 text-sm">
                      {primaryAnn ? (
                        <span className="text-green-700" title={primaryAnn.termUri}>
                          {primaryAnn.termLabel || primaryAnn.ontology}
                          <span className="text-gray-400 ml-1">
                            ({primaryAnn.score?.toFixed(2)})
                          </span>
                        </span>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="p-3 text-sm text-gray-600 max-w-md truncate">
                      {node.description ?? prov?.description ?? "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {pageInfo?.hasNextPage && (
        <button
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          onClick={() =>
            fetchMore({
              variables: { after: pageInfo.endCursor },
            })
          }
        >
          Load more
        </button>
      )}
    </div>
  );
}

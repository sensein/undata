"use client";

import { useQuery } from "@apollo/client";
import { useState } from "react";
import { BROWSE_ELEMENTS } from "@/graphql/queries";
import type { ElementEdge, OntologyAnnotation } from "@/graphql/types";

export default function ElementsPage() {
  const [source, setSource] = useState<string | undefined>();
  const [dataType, setDataType] = useState<string | undefined>();

  const { data, loading, error, fetchMore } = useQuery(BROWSE_ELEMENTS, {
    variables: { source, dataType, first: 50 },
  });

  const elements = data?.browseElements?.edges ?? [];
  const pageInfo = data?.browseElements?.pageInfo;
  const totalCount = data?.browseElements?.totalCount ?? 0;

  return (
    <div className="max-w-7xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Data Elements</h1>

      {/* Filters */}
      <div className="flex gap-4 mb-6">
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

        <span className="text-gray-500 self-center">
          {totalCount} elements
        </span>
      </div>

      {loading && <p className="text-gray-500">Loading...</p>}
      {error && <p className="text-red-500">Error: {error.message}</p>}

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
            {elements.map(({ node, cursor }: ElementEdge) => {
              const prov = node.provenance?.[0];
              const primaryAnn = node.ontologyAnnotations?.find(
                (a: OntologyAnnotation) => a.primary
              );
              return (
                <tr key={cursor} className="border-b hover:bg-gray-50">
                  <td className="p-3 font-mono text-sm">
                    {prov?.name ?? node.fileName}
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
                      <span
                        className="text-green-700"
                        title={primaryAnn.termUri}
                      >
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
                    {prov?.description ?? node.description ?? "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

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

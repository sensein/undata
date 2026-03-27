"use client";

import { useQuery } from "@apollo/client/react";
import { BROWSE_VALUES } from "@/graphql/queries";
import type { ValueConnection, Edge, ValueNode, OntologyAnnotation } from "@/graphql/types";

export default function ValuesPage() {
  const { data, loading, error } = useQuery<{ browseValues: ValueConnection }>(BROWSE_VALUES, {
    variables: { first: 50 },
  });

  const values = data?.browseValues?.edges ?? [];
  const totalCount = data?.browseValues?.totalCount ?? 0;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Values</h1>
      <p className="text-gray-500 mb-6">{totalCount} values</p>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 mb-6">
          <p className="text-red-800">Unable to load values: {error.message}</p>
        </div>
      )}

      {loading && !data && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      )}

      {!loading && !error && values.length === 0 && (
        <p className="text-gray-500 text-center py-12">No values found.</p>
      )}

      {values.length > 0 && (
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-100 border-b">
              <th className="text-left p-3">Label</th>
              <th className="text-left p-3">Source</th>
              <th className="text-left p-3">Type</th>
              <th className="text-left p-3">Ontology</th>
              <th className="text-left p-3">Description</th>
            </tr>
          </thead>
          <tbody>
            {values.map(({ node, cursor }: Edge<ValueNode>) => {
              const prov = node.provenance?.[0];
              const primaryAnn = node.ontologyAnnotations?.find((a: OntologyAnnotation) => a.primary);
              return (
                <tr key={cursor} className="border-b hover:bg-gray-50">
                  <td className="p-3 font-mono text-sm font-medium">{node.label}</td>
                  <td className="p-3">
                    {prov?.source && (
                      <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">{prov.source}</span>
                    )}
                  </td>
                  <td className="p-3 text-sm">{node.valueType ?? "—"}</td>
                  <td className="p-3 text-sm">
                    {primaryAnn ? (
                      <span className="text-green-700">{primaryAnn.termLabel}</span>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="p-3 text-sm text-gray-600 truncate max-w-md">{node.description ?? "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

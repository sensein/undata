"use client";

import { useQuery } from "@apollo/client";
import { useState } from "react";
import { BROWSE_VALUES } from "@/graphql/queries";
import type { ValueNode, OntologyAnnotation } from "@/graphql/types";

export default function ValuesPage() {
  const [source, setSource] = useState<string | undefined>();
  const { data, loading, error } = useQuery(BROWSE_VALUES, {
    variables: { source, first: 100 },
  });

  const values = data?.browseValues ?? [];

  return (
    <div className="max-w-7xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Values</h1>
      <div className="flex gap-4 mb-6">
        <select
          className="border rounded px-3 py-2"
          value={source ?? ""}
          onChange={(e) => setSource(e.target.value || undefined)}
        >
          <option value="">All sources</option>
          <option value="bids">BIDS</option>
          <option value="dandi">DANDI</option>
          <option value="openminds">openMINDS</option>
          <option value="aind">AIND</option>
        </select>
        <span className="text-gray-500 self-center">{values.length} values</span>
      </div>

      {loading && <p className="text-gray-500">Loading...</p>}
      {error && <p className="text-red-500">Error: {error.message}</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {values.map((v: ValueNode) => {
          const primaryAnn = v.ontologyAnnotations?.find((a: OntologyAnnotation) => a.primary);
          return (
            <div key={v.fileName} className="border rounded p-3 hover:bg-gray-50">
              <div className="font-mono text-sm font-medium">{v.label}</div>
              <div className="text-xs text-gray-500 mt-1">
                {v.provenance?.[0]?.source} · {v.valueType}
              </div>
              {(primaryAnn || v.ontologyId) && (
                <div className="text-xs text-green-700 mt-1">
                  {primaryAnn?.termLabel || v.ontologyId}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

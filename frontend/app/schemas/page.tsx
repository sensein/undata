"use client";

import { useQuery } from "@apollo/client/react";
import { BROWSE_SCHEMAS } from "@/graphql/queries";
import type { SchemaConnection, Edge, SchemaNode } from "@/graphql/types";

export default function SchemasPage() {
  const { data, loading, error } = useQuery<{ browseSchemas: SchemaConnection }>(BROWSE_SCHEMAS, {
    variables: { first: 50 },
  });

  const schemas = data?.browseSchemas?.edges ?? [];
  const totalCount = data?.browseSchemas?.totalCount ?? 0;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Schemas</h1>
      <p className="text-gray-500 mb-6">{totalCount} schemas</p>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4 mb-6">
          <p className="text-red-800">Unable to load schemas: {error.message}</p>
        </div>
      )}

      {loading && !data && (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      )}

      {!loading && !error && schemas.length === 0 && (
        <p className="text-gray-500 text-center py-12">No schemas found.</p>
      )}

      <div className="space-y-3">
        {schemas.map(({ node, cursor }: Edge<SchemaNode>) => {
          const prov = node.provenance?.[0];
          return (
            <div key={cursor} className="border rounded p-4">
              <div className="flex items-center gap-3 mb-2">
                <span className="font-mono font-medium">{prov?.name ?? node.fileName ?? node.sha256.slice(0, 12)}</span>
                {prov?.source && (
                  <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">{prov.source}</span>
                )}
                {node.isMixin && (
                  <span className="px-2 py-1 bg-purple-100 text-purple-800 rounded text-xs">mixin</span>
                )}
              </div>
              {node.description && <p className="text-gray-600 text-sm mb-2">{node.description}</p>}
              {node.properties.length > 0 && (
                <div className="text-xs text-gray-500">
                  Properties: {node.properties.join(", ")}
                </div>
              )}
              {node.subclassOf && (
                <div className="text-xs text-gray-500">Extends: {node.subclassOf}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

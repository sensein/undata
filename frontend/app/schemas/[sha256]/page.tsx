"use client";

import { useMemo } from "react";
import { useQuery } from "@apollo/client/react";
import { useParams } from "next/navigation";
import { GET_SCHEMA, BROWSE_ELEMENTS } from "@/graphql/queries";
import { EntityDetailLayout } from "@/components/EntityDetailLayout";
import { EntityTag } from "@/components/EntityTag";
import { SourceBadge } from "@/components/SourceBadge";
import type { SchemaNode, ElementConnection, Edge, ElementNode } from "@/graphql/types";
import Link from "next/link";

export default function SchemaDetailPage() {
  const params = useParams();
  const sha256 = params.sha256 as string;

  const { data, loading, error } = useQuery<{ schema_: SchemaNode | null }>(GET_SCHEMA, {
    variables: { sha256 },
  });

  // Load all elements to resolve property names → sha256
  const { data: elemData } = useQuery<{ browseElements: ElementConnection }>(BROWSE_ELEMENTS, {
    variables: { first: 200 },
  });

  const schema = data?.schema_;

  // Build a lookup: provenance name → element sha256
  const nameToElement = useMemo(() => {
    const map = new Map<string, { sha256: string; name: string; source: string; dataType: string }>();
    for (const edge of (elemData?.browseElements?.edges ?? []) as Edge<ElementNode>[]) {
      const e = edge.node;
      const prov = e.provenance?.[0];
      // Index by full sha256 and by sha256 prefix (first 12 chars)
      map.set(e.sha256, {
        sha256: e.sha256,
        name: prov?.name ?? e.sha256.slice(0, 12),
        source: prov?.source ?? "",
        dataType: e.dataType ?? "",
      });
      map.set(e.sha256.slice(0, 12), {
        sha256: e.sha256,
        name: prov?.name ?? e.sha256.slice(0, 12),
        source: prov?.source ?? "",
        dataType: e.dataType ?? "",
      });
      // Also index by name for backwards compat
      if (prov?.name) {
        map.set(prov.name, {
          sha256: e.sha256,
          name: prov.name,
          source: prov.source ?? "",
          dataType: e.dataType ?? "",
        });
      }
    }
    return map;
  }, [elemData]);

  if (loading) {
    return (
      <div className="space-y-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  if (error || !schema) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 text-lg">{error ? `Error: ${error.message}` : "Schema not found"}</p>
      </div>
    );
  }

  const prov = schema.provenance?.[0];

  return (
    <EntityDetailLayout
      entityType="schema"
      backHref="/schemas"
      backLabel="Back to schemas"
      title={prov?.name ?? schema.sha256.slice(0, 12)}
      source={prov?.source}
      sha256={schema.sha256}
      description={schema.description ?? prov?.description}
      provenance={schema.provenance}
      annotations={schema.ontologyAnnotations}
    >
      <div className="space-y-4">
        {schema.subclassOf && (
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500 uppercase">Extends</div>
            <div className="font-mono text-sm">{schema.subclassOf}</div>
          </div>
        )}
        {schema.isMixin && (
          <div className="inline-block px-3 py-1 bg-purple-100 text-purple-800 rounded text-sm font-medium">
            Mixin schema
          </div>
        )}

        {/* Properties as table with resolved element links */}
        {(schema.properties ?? []).length > 0 && (
          <div>
            <h3 className="text-md font-semibold mb-3">Properties ({schema.properties.length})</h3>
            <div className="border rounded overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b">
                    <th className="text-left p-2 font-medium">Name</th>
                    <th className="text-left p-2 font-medium">Type</th>
                    <th className="text-left p-2 font-medium">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {schema.properties.map((propRef: string, i: number) => {
                    // propRef may be a sha256 hash, sha256 prefix, or name
                    const resolved = nameToElement.get(propRef) || nameToElement.get(propRef.slice(0, 12));
                    return (
                      <tr key={i} className="border-b last:border-0 hover:bg-gray-50">
                        <td className="p-2">
                          {resolved ? (
                            <EntityTag entityType="elements" sha256={resolved.sha256} label={resolved.name} />
                          ) : (
                            <span className="text-gray-500 font-mono text-xs">{propRef.slice(0, 16)}...</span>
                          )}
                        </td>
                        <td className="p-2 text-gray-600">{resolved?.dataType ?? "—"}</td>
                        <td className="p-2">{resolved?.source ? <SourceBadge source={resolved.source} /> : "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </EntityDetailLayout>
  );
}

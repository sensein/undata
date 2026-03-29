"use client";

import { useMemo } from "react";
import { useQuery } from "@apollo/client/react";
import { useParams } from "next/navigation";
import { GET_VALUESET, BROWSE_VALUES } from "@/graphql/queries";
import { EntityDetailLayout } from "@/components/EntityDetailLayout";
import { EntityTag } from "@/components/EntityTag";
import { SourceBadge } from "@/components/SourceBadge";
import type { ValueConnection, Edge, ValueNode } from "@/graphql/types";

interface ValueSetData {
  sha256: string;
  name?: string;
  members: string[];
  description?: string;
  provenance: Array<{ source: string; className: string; name: string; description?: string }>;
  ontologyAnnotations: Array<{
    termUri: string; termLabel: string; ontology: string;
    mappingRelation: string; score: number; primary: boolean;
  }>;
}

export default function ValueSetDetailPage() {
  const params = useParams();
  const sha256 = params.sha256 as string;

  const { data, loading, error } = useQuery<{ valueset: ValueSetData | null }>(GET_VALUESET, {
    variables: { sha256 },
  });

  // Load values to resolve member sha256 → label
  const { data: valData } = useQuery<{ browseValues: ValueConnection }>(BROWSE_VALUES, {
    variables: { first: 2000 },
  });

  const valueset = data?.valueset;

  // Build lookup: sha256/label/name → value info
  // Members may be stored as value labels, provenance names, or sha256 hashes
  const shaToValue = useMemo(() => {
    const map = new Map<string, { sha256: string; label: string; source: string }>();
    for (const edge of (valData?.browseValues?.edges ?? []) as Edge<ValueNode>[]) {
      const v = edge.node;
      const info = { sha256: v.sha256, label: v.label ?? v.sha256.slice(0, 12), source: v.provenance?.[0]?.source ?? "" };
      map.set(v.sha256, info);
      map.set(v.sha256.slice(0, 12), info);
      // Index by label
      if (v.label) {
        map.set(v.label, info);
        map.set(v.label.toLowerCase(), info);
      }
      // Index by provenance name (members often stored as names)
      for (const prov of v.provenance ?? []) {
        if (prov.name && !map.has(prov.name)) {
          map.set(prov.name, { ...info, label: prov.name });
          map.set(prov.name.toLowerCase(), { ...info, label: prov.name });
        }
      }
    }
    return map;
  }, [valData]);

  if (loading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  if (error || !valueset) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 text-lg">{error ? `Error: ${error.message}` : "Value set not found"}</p>
      </div>
    );
  }

  const prov = valueset.provenance?.[0];

  return (
    <EntityDetailLayout
      entityType="valueset"
      backHref="/valuesets"
      backLabel="Back to value sets"
      title={valueset.name ?? valueset.sha256.slice(0, 12)}
      source={prov?.source}
      sha256={valueset.sha256}
      description={valueset.description ?? prov?.description}
      provenance={valueset.provenance}
      annotations={valueset.ontologyAnnotations}
    >
      {(valueset.members ?? []).length > 0 && (
        <div>
          <h3 className="text-md font-semibold mb-3">Members ({valueset.members.length})</h3>
          <div className="border rounded overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b">
                  <th className="text-left p-2 font-medium">Value</th>
                  <th className="text-left p-2 font-medium">Source</th>
                </tr>
              </thead>
              <tbody>
                {valueset.members.map((memberRef: string, i: number) => {
                  // memberRef may be sha256, sha256 prefix, or label
                  const resolved = shaToValue.get(memberRef)
                    || shaToValue.get(memberRef.slice(0, 12))
                    || shaToValue.get(memberRef.toLowerCase())
                    || shaToValue.get(memberRef.replace(/_/g, " ").toLowerCase());
                  return (
                    <tr key={i} className="border-b last:border-0 hover:bg-gray-50">
                      <td className="p-2">
                        {resolved ? (
                          <EntityTag entityType="values" sha256={resolved.sha256} label={resolved.label} />
                        ) : (
                          <span className="text-gray-500 font-mono text-xs">{memberRef.slice(0, 16)}...</span>
                        )}
                      </td>
                      <td className="p-2">{resolved?.source ? <SourceBadge source={resolved.source} /> : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </EntityDetailLayout>
  );
}

"use client";

import { useQuery } from "@apollo/client/react";
import { useParams } from "next/navigation";
import { GET_VALUESET } from "@/graphql/queries";
import { EntityDetailLayout } from "@/components/EntityDetailLayout";
import { EntityTag } from "@/components/EntityTag";
import type { ValueSetNode } from "@/graphql/types";

// Type alias for the valueset node extending with optional fields
interface ValueSetData {
  sha256: string;
  name?: string;
  members: string[];
  description?: string;
  semantic?: Record<string, unknown>;
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

  const valueset = data?.valueset;

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

  // Members are stored as identifiers (name_hashprefix)
  const memberValues = (valueset.members ?? []).map((m: string) => {
    const parts = m.split("_");
    const hashPart = parts[parts.length - 1] ?? m;
    const namePart = parts.slice(0, -1).join("_") || m;
    return { entityType: "values", sha256: hashPart, label: namePart };
  });

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
      {memberValues.length > 0 && (
        <div>
          <h3 className="text-md font-semibold mb-3">Members ({memberValues.length})</h3>
          <div className="flex flex-wrap gap-2">
            {memberValues.map((v, i) => (
              <EntityTag key={i} entityType={v.entityType} sha256={v.sha256} label={v.label} />
            ))}
          </div>
        </div>
      )}
    </EntityDetailLayout>
  );
}

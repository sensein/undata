"use client";

import { useQuery } from "@apollo/client/react";
import { useParams } from "next/navigation";
import { GET_VALUESET } from "@/graphql/queries";
import { EntityDetailLayout } from "@/components/EntityDetailLayout";
import { ValueMemberTable } from "@/components/PropertyTable";

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
        <ValueMemberTable members={valueset.members} />
      )}
    </EntityDetailLayout>
  );
}

"use client";

import { useQuery } from "@apollo/client/react";
import { useParams } from "next/navigation";
import { GET_VALUE } from "@/graphql/queries";
import { EntityDetailLayout } from "@/components/EntityDetailLayout";
import type { ValueNode } from "@/graphql/types";

export default function ValueDetailPage() {
  const params = useParams();
  const sha256 = params.sha256 as string;

  const { data, loading, error } = useQuery<{ value: ValueNode | null }>(GET_VALUE, {
    variables: { sha256 },
  });

  const value = data?.value;

  if (loading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  if (error || !value) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 text-lg">{error ? `Error: ${error.message}` : "Value not found"}</p>
      </div>
    );
  }

  const prov = value.provenance?.[0];

  return (
    <EntityDetailLayout
      entityType="value"
      backHref="/values"
      backLabel="Back to values"
      title={value.label ?? value.sha256.slice(0, 12)}
      source={prov?.source}
      sha256={value.sha256}
      description={value.description ?? prov?.description}
      provenance={value.provenance}
      annotations={value.ontologyAnnotations}
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {value.valueType && (
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500 uppercase">Value Type</div>
            <div>{value.valueType}</div>
          </div>
        )}
        {value.ontologyId && (
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500 uppercase">Ontology ID</div>
            <div className="font-mono text-sm">{value.ontologyId}</div>
          </div>
        )}
      </div>
    </EntityDetailLayout>
  );
}

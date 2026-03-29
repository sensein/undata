"use client";

import { useQuery } from "@apollo/client/react";
import { useParams } from "next/navigation";
import { GET_SCHEMA } from "@/graphql/queries";
import { EntityDetailLayout } from "@/components/EntityDetailLayout";
import { ElementPropertyTable } from "@/components/PropertyTable";
import type { SchemaNode } from "@/graphql/types";

export default function SchemaDetailPage() {
  const params = useParams();
  const sha256 = params.sha256 as string;

  const { data, loading, error } = useQuery<{ schema_: SchemaNode | null }>(GET_SCHEMA, {
    variables: { sha256 },
  });

  const schema = data?.schema_;

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
      <div className="space-y-3">
        {schema.subclassOf && (
          <div className="border rounded p-2">
            <div className="text-xs text-gray-500 uppercase">Extends</div>
            <div className="font-mono text-sm">{schema.subclassOf}</div>
          </div>
        )}
        {schema.isMixin && (
          <div className="inline-block px-2 py-0.5 bg-purple-100 text-purple-800 rounded text-xs font-medium">
            Mixin schema
          </div>
        )}

        {(schema.properties ?? []).length > 0 && (
          <ElementPropertyTable
            properties={schema.properties}
            schemaSource={prov?.source}
            schemaClass={prov?.className}
          />
        )}
      </div>
    </EntityDetailLayout>
  );
}

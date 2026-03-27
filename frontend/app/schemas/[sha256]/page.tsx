"use client";

import { useQuery } from "@apollo/client/react";
import { useParams } from "next/navigation";
import { GET_SCHEMA } from "@/graphql/queries";
import { EntityDetailLayout } from "@/components/EntityDetailLayout";
import { EntityTag } from "@/components/EntityTag";
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

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded p-4">
        <p className="text-red-800">Unable to load schema: {error.message}</p>
      </div>
    );
  }

  if (!schema) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 text-lg">Schema not found</p>
        <p className="text-gray-400 text-sm mt-1 font-mono">{sha256}</p>
      </div>
    );
  }

  const prov = schema.provenance?.[0];

  // Extract sha256 prefixes from property identifiers (format: name_hashprefix)
  const propertyElements = (schema.properties ?? []).map((prop: string) => {
    const parts = prop.split("_");
    const hashPart = parts[parts.length - 1] ?? prop;
    const namePart = parts.slice(0, -1).join("_") || prop;
    return { entityType: "elements", sha256: hashPart, label: namePart };
  });

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
      {/* Schema properties */}
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

        {/* Properties as clickable element links */}
        {propertyElements.length > 0 && (
          <div>
            <h3 className="text-md font-semibold mb-3">Properties ({propertyElements.length})</h3>
            <div className="flex flex-wrap gap-2">
              {propertyElements.map((prop, i) => (
                <EntityTag
                  key={i}
                  entityType={prop.entityType}
                  sha256={prop.sha256}
                  label={prop.label}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </EntityDetailLayout>
  );
}

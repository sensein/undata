"use client";

import { useQuery } from "@apollo/client/react";
import { useParams } from "next/navigation";
import { GET_SCHEMA, BROWSE_SCHEMAS, FLAGS_FOR_ENTITY } from "@/graphql/queries";
import { EntityDetailLayout } from "@/components/EntityDetailLayout";
import { EntityTag } from "@/components/EntityTag";
import { ElementPropertyTable } from "@/components/PropertyTable";
import { getStatusColor } from "@/lib/source-colors";
import type { SchemaNode, SchemaConnection, CurationFlagConnection, Edge, CurationFlagNode } from "@/graphql/types";
import { useMemo } from "react";

export default function SchemaDetailPage() {
  const params = useParams();
  const sha256 = params.sha256 as string;

  const { data, loading, error } = useQuery<{ schema_: SchemaNode | null }>(GET_SCHEMA, {
    variables: { sha256 },
  });

  // Load all schemas to resolve subclass_of name → sha256
  const { data: allSchemas } = useQuery<{ browseSchemas: SchemaConnection }>(BROWSE_SCHEMAS, {
    variables: { first: 500 },
  });

  // Load flags for this entity
  const { data: flagsData } = useQuery<{ flagsForEntity: CurationFlagConnection }>(FLAGS_FOR_ENTITY, {
    variables: { entityType: "schema", entityRef: sha256 },
    skip: !data?.schema_,
  });

  const schema = data?.schema_;

  // Resolve subclass_of name to a schema sha256
  const parentSchema = useMemo(() => {
    if (!schema?.subclassOf || !allSchemas) return null;
    for (const edge of (allSchemas.browseSchemas?.edges ?? []) as Edge<SchemaNode>[]) {
      const s = edge.node;
      const name = s.provenance?.[0]?.name;
      if (name === schema.subclassOf) return { sha256: s.sha256, name };
    }
    return null;
  }, [schema, allSchemas]);

  const flags = (flagsData?.flagsForEntity?.edges ?? []) as Edge<CurationFlagNode>[];

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
            <div className="text-sm">
              {parentSchema ? (
                <EntityTag entityType="schemas" sha256={parentSchema.sha256} label={parentSchema.name} />
              ) : (
                <span className="font-mono">{schema.subclassOf}</span>
              )}
            </div>
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

        {flags.length > 0 && (
          <div>
            <div className="text-xs text-gray-500 mb-1">Curation Flags ({flags.length})</div>
            <div className="space-y-1">
              {flags.map((e) => {
                const f = e.node;
                const { bg, text: textColor } = getStatusColor(f.status);
                return (
                  <div key={f.id} className="flex items-center gap-2 text-xs">
                    <span className={`px-1.5 py-0.5 rounded ${bg} ${textColor}`}>{f.status}</span>
                    <span className="text-gray-600">{f.flagType}</span>
                    <span className="text-gray-400 truncate max-w-xs">{(f.context as Record<string, string>)?.reason ?? ""}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </EntityDetailLayout>
  );
}

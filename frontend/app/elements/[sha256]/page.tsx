"use client";

import { useQuery } from "@apollo/client/react";
import { useParams } from "next/navigation";
import { GET_ELEMENT, BROWSE_SCHEMAS } from "@/graphql/queries";
import { EntityDetailLayout } from "@/components/EntityDetailLayout";
import { RelatedEntities } from "@/components/RelatedEntities";
import type { ElementNode, SchemaConnection, Edge, SchemaNode } from "@/graphql/types";
import { useMemo } from "react";

export default function ElementDetailPage() {
  const params = useParams();
  const sha256 = params.sha256 as string;

  const { data, loading, error } = useQuery<{ element: ElementNode | null }>(GET_ELEMENT, {
    variables: { sha256 },
  });

  // Load schemas to find which ones reference this element
  const { data: schemasData } = useQuery<{ browseSchemas: SchemaConnection }>(BROWSE_SCHEMAS, {
    variables: { first: 100 },
  });

  const element = data?.element;

  const relatedSchemas = useMemo(() => {
    if (!element || !schemasData) return [];
    const schemas = schemasData.browseSchemas?.edges ?? [];
    return schemas
      .filter((e: Edge<SchemaNode>) =>
        e.node.properties?.some((p: string) => p.includes(sha256.slice(0, 12))),
      )
      .map((e: Edge<SchemaNode>) => ({
        entityType: "schemas",
        sha256: e.node.sha256,
        label: e.node.provenance?.[0]?.name ?? e.node.sha256.slice(0, 12),
      }));
  }, [element, schemasData, sha256]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 bg-gray-100 rounded animate-pulse" />
        <div className="h-4 w-96 bg-gray-100 rounded animate-pulse" />
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-20 bg-gray-100 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded p-4">
        <p className="text-red-800">Unable to load element: {error.message}</p>
      </div>
    );
  }

  if (!element) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 text-lg">Element not found</p>
        <p className="text-gray-400 text-sm mt-1 font-mono">{sha256}</p>
      </div>
    );
  }

  const prov = element.provenance?.[0];

  return (
    <EntityDetailLayout
      entityType="element"
      backHref="/elements"
      backLabel="Back to elements"
      title={prov?.name ?? element.fileName ?? element.sha256.slice(0, 12)}
      source={prov?.source}
      sha256={element.sha256}
      description={element.description ?? prov?.description}
      provenance={element.provenance}
      annotations={element.ontologyAnnotations}
      relatedContent={
        <RelatedEntities title="Used in schemas" items={relatedSchemas} />
      }
    >
      {/* Semantic properties — compact 3-column grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
        <div className="border rounded p-2">
          <div className="text-[10px] text-gray-500 uppercase">Data Type</div>
          <div className="font-mono text-sm">{element.dataType ?? "—"}</div>
        </div>
        {element.unit && (
          <div className="border rounded p-2">
            <div className="text-[10px] text-gray-500 uppercase">Unit</div>
            <div className="text-sm">
              {element.unit}
              {element.unitUri && (
                <a href={element.unitUri} target="_blank" rel="noopener noreferrer" className="ml-1 text-[10px] text-blue-600 hover:underline">↗ QUDT</a>
              )}
            </div>
          </div>
        )}
        {element.pattern && (
          <div className="border rounded p-2">
            <div className="text-[10px] text-gray-500 uppercase">Pattern</div>
            <div className="font-mono text-xs truncate" title={element.pattern}>{element.pattern}</div>
          </div>
        )}
        {element.valueDomain && (
          <div className="border rounded p-2">
            <div className="text-[10px] text-gray-500 uppercase">Value Domain</div>
            <div className="text-sm">{element.valueDomain}</div>
          </div>
        )}
        {element.minValue != null && (
          <div className="border rounded p-2">
            <div className="text-[10px] text-gray-500 uppercase">Min Value</div>
            <div className="text-sm">{element.minValue}</div>
          </div>
        )}
        {element.maxValue != null && (
          <div className="border rounded p-2">
            <div className="text-[10px] text-gray-500 uppercase">Max Value</div>
            <div className="text-sm">{element.maxValue}</div>
          </div>
        )}
      </div>
    </EntityDetailLayout>
  );
}

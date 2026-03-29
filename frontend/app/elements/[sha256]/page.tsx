"use client";

import { useQuery } from "@apollo/client/react";
import { useParams } from "next/navigation";
import { GET_ELEMENT, SCHEMAS_USING_ELEMENT, TRANSFORMS_FOR_ELEMENT, FLAGS_FOR_ENTITY } from "@/graphql/queries";
import { EntityDetailLayout } from "@/components/EntityDetailLayout";
import { EntityTag } from "@/components/EntityTag";
import type { ElementNode, SchemaConnection, TransformConnection, CurationFlagConnection, Edge, SchemaNode, TransformNode, CurationFlagNode } from "@/graphql/types";
import { getStatusColor } from "@/lib/source-colors";

export default function ElementDetailPage() {
  const params = useParams();
  const sha256 = params.sha256 as string;

  const { data, loading, error } = useQuery<{ element: ElementNode | null }>(GET_ELEMENT, {
    variables: { sha256 },
  });

  const { data: schemasData } = useQuery<{ schemasUsingElement: SchemaConnection }>(SCHEMAS_USING_ELEMENT, {
    variables: { sha256 },
    skip: !data?.element,
  });

  const { data: transformsData } = useQuery<{ transformsForElement: TransformConnection }>(TRANSFORMS_FOR_ELEMENT, {
    variables: { sha256 },
    skip: !data?.element,
  });

  const { data: flagsData } = useQuery<{ flagsForEntity: CurationFlagConnection }>(FLAGS_FOR_ENTITY, {
    variables: { entityType: "element", entityRef: sha256 },
    skip: !data?.element,
  });

  const element = data?.element;

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 bg-gray-100 rounded animate-pulse" />
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-20 bg-gray-100 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  if (error || !element) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 text-lg">{error ? `Error: ${error.message}` : "Element not found"}</p>
      </div>
    );
  }

  const prov = element.provenance?.[0];
  const schemas = (schemasData?.schemasUsingElement?.edges ?? []) as Edge<SchemaNode>[];
  const transforms = (transformsData?.transformsForElement?.edges ?? []) as Edge<TransformNode>[];
  const flags = (flagsData?.flagsForEntity?.edges ?? []) as Edge<CurationFlagNode>[];

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

      {/* Cross-references */}
      {schemas.length > 0 && (
        <div className="mt-3">
          <div className="text-xs text-gray-500 mb-1">Used in Schemas ({schemas.length})</div>
          <div className="flex flex-wrap gap-1">
            {schemas.map((e) => (
              <EntityTag key={e.node.sha256} entityType="schemas" sha256={e.node.sha256} label={e.node.provenance?.[0]?.name ?? e.node.sha256.slice(0, 12)} />
            ))}
          </div>
        </div>
      )}

      {transforms.length > 0 && (
        <div className="mt-3">
          <div className="text-xs text-gray-500 mb-1">Transforms ({transforms.length})</div>
          <div className="space-y-1">
            {transforms.map((e) => {
              const t = e.node;
              const isSrc = t.sourceElement.includes(sha256);
              const otherUri = isSrc ? t.targetElement : t.sourceElement;
              const otherKey = otherUri.includes("/") ? otherUri.split("/").pop()! : otherUri;
              const otherSha = otherKey.includes("_") ? otherKey.split("_").pop()! : otherKey.slice(0, 12);
              const otherName = otherKey.includes("_") ? otherKey.split("_")[0] : otherKey.slice(0, 12);
              return (
                <div key={t.sha256} className="flex items-center gap-1 text-xs">
                  <span className="text-gray-400">{isSrc ? "→" : "←"}</span>
                  <EntityTag entityType="elements" sha256={otherSha} label={otherName} />
                  <span className="px-1 py-0.5 bg-gray-100 rounded text-[10px]">{t.functionType ?? "unknown"}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {flags.length > 0 && (
        <div className="mt-3">
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
    </EntityDetailLayout>
  );
}

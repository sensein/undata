"use client";

import { useQuery } from "@apollo/client/react";
import { GET_ELEMENT, GET_SCHEMA, GET_VALUE, GET_VALUESET } from "@/graphql/queries";
import { SourceBadge } from "@/components/SourceBadge";
import type { OntologyAnnotation, ProvenanceEntry } from "@/graphql/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
const QUERIES: Record<string, { query: any; key: string }> = {
  element: { query: GET_ELEMENT, key: "element" },
  schema: { query: GET_SCHEMA, key: "schema_" },
  value: { query: GET_VALUE, key: "value" },
  valueset: { query: GET_VALUESET, key: "valueset" },
};

interface Props {
  entityType: string;
  entityRef: string;
}

export function EntityInlineDetail({ entityType, entityRef }: Props) {
  const config = QUERIES[entityType.toLowerCase()];
  const { data, loading } = useQuery(config?.query ?? GET_ELEMENT, {
    variables: { sha256: entityRef },
    skip: !config,
  });

  if (loading) return <div className="text-xs text-gray-400 py-2">Loading entity details...</div>;

  const entity = (data as any)?.[config?.key ?? "element"];
  if (!entity) return <div className="text-xs text-gray-400 py-2">Entity not found</div>;

  const prov: ProvenanceEntry | undefined = entity.provenance?.[0];
  const anns: OntologyAnnotation[] = entity.ontologyAnnotations ?? [];

  return (
    <div className="bg-white border rounded p-3 text-xs space-y-2">
      {/* Header */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-semibold text-sm">{prov?.name ?? entity.sha256?.slice(0, 12)}</span>
        {prov?.source && <SourceBadge source={prov.source} />}
        {prov?.className && <span className="text-gray-400">::{prov.className}</span>}
      </div>

      {/* Descriptions from all provenance entries */}
      {entity.provenance?.some((p: ProvenanceEntry) => p.description) && (
        <p className="text-gray-600">
          {(entity.provenance as ProvenanceEntry[])
            .map((p) => p.description)
            .filter(Boolean)
            .join(" | ")}
        </p>
      )}

      {/* Semantic fields */}
      <div className="flex flex-wrap gap-3">
        {entity.dataType && (
          <span><span className="text-gray-400">Type:</span> <span className="font-mono">{entity.dataType}</span></span>
        )}
        {entity.unit && (
          <span><span className="text-gray-400">Unit:</span> {entity.unit}</span>
        )}
        {entity.pattern && (
          <span><span className="text-gray-400">Pattern:</span> <span className="font-mono truncate max-w-[200px] inline-block align-bottom">{entity.pattern}</span></span>
        )}
        {entity.valueDomain && (
          <span><span className="text-gray-400">Domain:</span> {entity.valueDomain}</span>
        )}
        {entity.minValue != null && (
          <span><span className="text-gray-400">Min:</span> {entity.minValue}</span>
        )}
        {entity.maxValue != null && (
          <span><span className="text-gray-400">Max:</span> {entity.maxValue}</span>
        )}
        {entity.label && (
          <span><span className="text-gray-400">Label:</span> {entity.label}</span>
        )}
        {entity.properties?.length > 0 && (
          <span><span className="text-gray-400">Properties:</span> {entity.properties.length}</span>
        )}
        {entity.members?.length > 0 && (
          <span><span className="text-gray-400">Members:</span> {entity.members.length}</span>
        )}
      </div>

      {/* Ontology annotations */}
      {anns.length > 0 && (
        <div className="flex flex-wrap gap-1">
          <span className="text-gray-400">Ontology:</span>
          {anns.slice(0, 5).map((a, i) => (
            <a
              key={i}
              href={a.termUri}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-0.5 px-1 py-0.5 bg-green-50 text-green-800 rounded text-[10px] hover:bg-green-100"
            >
              {a.ontology}:{a.termLabel} {a.mappingRelation?.replace("skos:", "")} {a.score?.toFixed(2)} ↗
            </a>
          ))}
          {anns.length > 5 && <span className="text-gray-400">+{anns.length - 5} more</span>}
        </div>
      )}

      <div className="font-mono text-[10px] text-gray-300">{entity.sha256}</div>
    </div>
  );
}

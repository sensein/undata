"use client";

import { useQuery } from "@apollo/client/react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { GET_ELEMENT } from "@/graphql/queries";
import type { ElementNode } from "@/graphql/types";

export default function ElementDetailPage() {
  const params = useParams();
  const sha256 = params.sha256 as string;

  const { data, loading, error } = useQuery<{
    element: ElementNode | null;
  }>(GET_ELEMENT, { variables: { sha256 } });

  const element = data?.element;

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 bg-gray-100 rounded animate-pulse" />
        <div className="h-4 w-96 bg-gray-100 rounded animate-pulse" />
        <div className="grid grid-cols-2 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-20 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded p-4">
        <p className="text-red-800 font-medium">Unable to load element</p>
        <p className="text-red-600 text-sm mt-1">{error.message}</p>
        <Link href="/elements" className="text-sm text-blue-600 underline mt-2 block">
          Back to elements
        </Link>
      </div>
    );
  }

  if (!element) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 text-lg">Element not found</p>
        <p className="text-gray-400 text-sm mt-1 font-mono">{sha256}</p>
        <Link href="/elements" className="text-blue-600 underline mt-4 block">
          Back to elements
        </Link>
      </div>
    );
  }

  const prov = element.provenance?.[0];

  return (
    <div className="max-w-4xl">
      <Link href="/elements" className="text-sm text-gray-500 hover:text-gray-700 mb-4 block">
        ← Back to elements
      </Link>

      <h1 className="text-2xl font-bold mb-2 font-mono">
        {prov?.name ?? element.fileName ?? element.sha256.slice(0, 12)}
      </h1>
      <p className="text-gray-500 mb-6">
        {[prov?.source, prov?.className, element.dataType].filter(Boolean).join(" · ")}
      </p>

      {(element.description || prov?.description) && (
        <p className="text-gray-700 mb-6">{element.description ?? prov?.description}</p>
      )}

      {/* Semantic Properties */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="border rounded p-3">
          <div className="text-xs text-gray-500 uppercase">Data Type</div>
          <div>{element.dataType ?? "—"}</div>
        </div>
        {element.unit && (
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500 uppercase">Unit</div>
            <div>{element.unit}</div>
          </div>
        )}
        {element.pattern && (
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500 uppercase">Pattern</div>
            <div className="font-mono text-sm">{element.pattern}</div>
          </div>
        )}
        {element.valueDomain && (
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500 uppercase">Value Domain</div>
            <div>{element.valueDomain}</div>
          </div>
        )}
        {element.minValue != null && (
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500 uppercase">Min Value</div>
            <div>{element.minValue}</div>
          </div>
        )}
        {element.maxValue != null && (
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500 uppercase">Max Value</div>
            <div>{element.maxValue}</div>
          </div>
        )}
        <div className="border rounded p-3 col-span-2">
          <div className="text-xs text-gray-500 uppercase">SHA-256</div>
          <div className="font-mono text-xs break-all">{element.sha256}</div>
        </div>
      </div>

      {/* Ontology Annotations */}
      {element.ontologyAnnotations?.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">Ontology Annotations</h2>
          <div className="space-y-2">
            {element.ontologyAnnotations.map((ann, i) => (
              <div key={i} className="border rounded p-3 flex justify-between items-center">
                <div>
                  <span className="font-medium">{ann.termLabel || ann.termUri}</span>
                  <span className="text-gray-400 ml-2 text-xs">{ann.ontology}</span>
                  <span className="text-gray-400 ml-2 text-xs">{ann.mappingRelation}</span>
                  {ann.matchLevel && (
                    <span className="text-gray-400 ml-2 text-xs">({ann.matchLevel})</span>
                  )}
                </div>
                <span className="text-sm font-mono">{ann.score.toFixed(3)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Provenance */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold mb-3">Provenance ({element.provenance.length})</h2>
        <div className="space-y-2">
          {element.provenance.map((p, i) => (
            <div key={i} className="border rounded p-3 text-sm">
              <div className="flex gap-4">
                <div>
                  <span className="text-gray-500">Source:</span>{" "}
                  <span className="font-medium">{p.source}</span>
                </div>
                <div>
                  <span className="text-gray-500">Class:</span> {p.className}
                </div>
                <div>
                  <span className="text-gray-500">Name:</span> {p.name}
                </div>
              </div>
              {p.description && <div className="text-gray-600 mt-1">{p.description}</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

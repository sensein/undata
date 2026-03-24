"use client";

import { useQuery } from "@apollo/client/react";
import { gql } from "@apollo/client";
import { useParams } from "next/navigation";

const GET_ELEMENT = gql`
  query GetElement($sha256: String!) {
    element(sha256: $sha256) {
      sha256
      dataType
      unit
      pattern
      valueDomain
      description
      minValue
      maxValue
      typeRef
      ontologyAnnotations {
        termUri
        termLabel
        ontology
        mappingRelation
        score
        primary
      }
      provenance {
        source
        className
        name
        description
      }
      fileName
    }
  }
`;

interface ElementDetail {
  sha256?: string;
  dataType?: string;
  unit?: string;
  valueDomain?: string;
  description?: string;
  minValue?: number;
  maxValue?: number;
  typeRef?: string;
  ontologyAnnotations: {
    termUri: string;
    termLabel: string;
    ontology: string;
    mappingRelation: string;
    score: number;
    primary: boolean;
  }[];
  provenance: {
    source: string;
    className: string;
    name: string;
    description?: string;
  }[];
  fileName: string;
}

export default function ElementDetailPage() {
  const params = useParams();
  const sha256 = params.sha256 as string;

  const { data, loading, error } = useQuery<{
    element: ElementDetail | null;
  }>(GET_ELEMENT, { variables: { sha256 } });

  const element = data?.element;

  if (loading) return <p className="p-6 text-gray-500">Loading...</p>;
  if (error) return <p className="p-6 text-red-500">Error: {error.message}</p>;
  if (!element) return <p className="p-6 text-gray-500">Element not found</p>;

  const prov = element.provenance?.[0];

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-2 font-mono">{prov?.name}</h1>
      <p className="text-gray-500 mb-6">
        {prov?.source} · {prov?.className} · {element.dataType}
      </p>

      {prov?.description && (
        <p className="text-gray-700 mb-6">{prov.description}</p>
      )}

      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="border rounded p-3">
          <div className="text-xs text-gray-500 uppercase">Data Type</div>
          <div>{element.dataType}</div>
        </div>
        {element.unit && (
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500 uppercase">Unit</div>
            <div>{element.unit}</div>
          </div>
        )}
        {element.valueDomain && (
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500 uppercase">Value Domain</div>
            <div>{element.valueDomain}</div>
          </div>
        )}
        {element.sha256 && (
          <div className="border rounded p-3">
            <div className="text-xs text-gray-500 uppercase">SHA-256</div>
            <div className="font-mono text-xs">{element.sha256}</div>
          </div>
        )}
      </div>

      {element.ontologyAnnotations?.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">Ontology Annotations</h2>
          <div className="space-y-2">
            {element.ontologyAnnotations.map((ann, i) => (
              <div key={i} className="border rounded p-3 flex justify-between">
                <div>
                  <span className="font-medium">
                    {ann.termLabel || ann.termUri}
                  </span>
                  <span className="text-gray-400 ml-2 text-xs">
                    {ann.ontology}
                  </span>
                  <span className="text-gray-400 ml-2 text-xs">
                    {ann.mappingRelation}
                  </span>
                </div>
                <span className="text-sm">{ann.score.toFixed(3)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mb-6">
        <h2 className="text-lg font-semibold mb-3">Provenance</h2>
        <div className="space-y-2">
          {element.provenance.map((p, i) => (
            <div key={i} className="border rounded p-3 text-sm">
              <div>
                <strong>Source:</strong> {p.source}
              </div>
              <div>
                <strong>Class:</strong> {p.className}
              </div>
              <div>
                <strong>Name:</strong> {p.name}
              </div>
              {p.description && (
                <div className="text-gray-600 mt-1">{p.description}</div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

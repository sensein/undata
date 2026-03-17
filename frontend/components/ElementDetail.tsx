"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DataElement } from "@/lib/types";

interface ElementDetailProps {
  element: DataElement;
}

export function ElementDetail({ element }: ElementDetailProps) {
  const { semantic, provenance } = element;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">
          {provenance[0]?.name || "Unknown"}
        </h1>
        <p className="mt-1 font-mono text-sm text-muted-foreground">
          {element.uri}
        </p>
        {provenance.length > 1 && (
          <Badge variant="secondary" className="mt-2">
            {provenance.length} sources
          </Badge>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Semantic Identity</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <dt className="text-muted-foreground">Data Type</dt>
            <dd>
              <Badge variant="outline">{semantic.data_type}</Badge>
            </dd>

            {semantic.ontology_term && (
              <>
                <dt className="text-muted-foreground">Ontology Term</dt>
                <dd className="break-all font-mono text-xs">
                  {semantic.ontology_term}
                </dd>
              </>
            )}

            {semantic.unit && (
              <>
                <dt className="text-muted-foreground">Unit</dt>
                <dd>{semantic.unit}</dd>
              </>
            )}

            {semantic.constraints && Object.keys(semantic.constraints).length > 0 && (
              <>
                <dt className="text-muted-foreground">Constraints</dt>
                <dd>
                  <pre className="rounded bg-muted p-2 text-xs">
                    {JSON.stringify(semantic.constraints, null, 2)}
                  </pre>
                </dd>
              </>
            )}
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Provenance ({provenance.length} source
            {provenance.length !== 1 ? "s" : ""})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {provenance.map((p, i) => (
              <div
                key={`${p.source}-${p.name}-${i}`}
                className="rounded border p-3"
              >
                <div className="flex items-center gap-2">
                  <Badge>{p.source}</Badge>
                  <span className="font-medium">
                    {p.class}.{p.name}
                  </span>
                </div>
                {p.description && (
                  <p className="mt-1 text-sm text-muted-foreground">
                    {p.description}
                  </p>
                )}
                <div className="mt-1 flex gap-3 text-xs text-muted-foreground">
                  {p.required && <span>required</span>}
                  {p.multivalued && <span>multivalued</span>}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

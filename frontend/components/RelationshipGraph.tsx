"use client";

import type { DataElement } from "@/lib/types";

interface RelationshipGraphProps {
  element: DataElement;
}

export function RelationshipGraph({ element }: RelationshipGraphProps) {
  // Simplified view: show provenance sources as related nodes
  const name = element.provenance[0]?.name || "unknown";

  return (
    <div className="rounded-md border p-6">
      <h3 className="mb-4 text-sm font-medium text-muted-foreground">
        Provenance Graph
      </h3>
      <div className="flex flex-wrap items-center justify-center gap-4">
        {/* Central element node */}
        <div className="rounded-lg bg-blue-100 px-4 py-2 text-center text-sm font-medium text-blue-800">
          {name}
          <div className="text-xs text-blue-600">{element.semantic.data_type}</div>
        </div>

        {/* Source nodes */}
        {element.provenance.map((p, i) => (
          <div key={`${p.source}-${i}`} className="flex items-center gap-2">
            <span className="text-muted-foreground">&larr;</span>
            <div className="rounded-lg bg-gray-100 px-3 py-1.5 text-center text-xs">
              <div className="font-medium">{p.source}</div>
              <div className="text-muted-foreground">{p.class}.{p.name}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

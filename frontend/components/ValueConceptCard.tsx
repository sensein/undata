import { Badge } from "@/components/ui/badge";
import type { ValueConceptResponse } from "@/lib/types";

interface ValueConceptCardProps {
  value: ValueConceptResponse;
}

export function ValueConceptCard({ value }: ValueConceptCardProps) {
  return (
    <div className="rounded-md border p-4">
      <div className="flex items-center justify-between">
        <span className="font-medium">{value.semantic.label}</span>
        <Badge variant="secondary">{value.provenance.length} source{value.provenance.length !== 1 ? "s" : ""}</Badge>
      </div>

      {value.semantic.ontology_term && (
        <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
          {value.semantic.ontology_term}
        </p>
      )}

      <div className="mt-2 flex flex-wrap gap-1">
        {value.provenance.map((p, i) => (
          <Badge key={`${p.source}-${i}`} variant="outline" className="text-xs">
            {p.source}: &quot;{p.raw_value}&quot;
          </Badge>
        ))}
      </div>
    </div>
  );
}

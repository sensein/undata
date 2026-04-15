import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ElementMappingResponse } from "@/lib/types";

interface MappingExplorerProps {
  mappings: ElementMappingResponse[];
}

export function MappingExplorer({ mappings }: MappingExplorerProps) {
  if (mappings.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-muted-foreground">
        No mappings found.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {mappings.map((m) => (
        <Card key={m.id}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">
              <Badge variant="secondary">{m.function_type}</Badge>
              {m.sssom_predicate && (
                <Badge variant="outline" className="ml-2">
                  {m.sssom_predicate}
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div>
              <span className="text-muted-foreground">Source:</span>{" "}
              <code className="break-all text-xs">
                {m.source_element_uri.split("/").pop()}
              </code>
            </div>
            <div>
              <span className="text-muted-foreground">Target:</span>{" "}
              <code className="break-all text-xs">
                {m.target_element_uri.split("/").pop()}
              </code>
            </div>
            {m.expression && (
              <div>
                <span className="text-muted-foreground">Transform:</span>{" "}
                <code className="rounded bg-muted px-2 py-0.5 text-xs">
                  {m.expression}
                </code>
                {m.expression_type && (
                  <span className="ml-1 text-xs text-muted-foreground">
                    ({m.expression_type})
                  </span>
                )}
              </div>
            )}
            {m.confidence !== null && m.confidence !== undefined && (
              <div>
                <span className="text-muted-foreground">Confidence:</span>{" "}
                {(m.confidence * 100).toFixed(0)}%
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

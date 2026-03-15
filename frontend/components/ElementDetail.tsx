import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RelationshipGraph } from "@/components/RelationshipGraph";
import type { DataElementDetail as ElementDetailType } from "@/lib/types";
import Link from "next/link";

interface Props {
  element: ElementDetailType;
}

export function ElementDetail({ element }: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{element.name}</h1>
        <div className="mt-2 flex gap-2">
          <Badge variant="outline">{element.data_type}</Badge>
          <Badge variant="secondary">{element.source.name}</Badge>
          {element.required && <Badge>required</Badge>}
          {element.multivalued && <Badge variant="outline">multi</Badge>}
        </div>
      </div>

      {element.description && (
        <p className="text-muted-foreground">{element.description}</p>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Metadata</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Row label="Version" value={String(element.version_num)} />
            <Row label="Created" value={element.created_at} />
            {element.allowed_values && (
              <Row
                label="Allowed values"
                value={element.allowed_values.join(", ")}
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Aliases ({element.alias_groups.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {element.alias_groups.length === 0 ? (
              <p className="text-sm text-muted-foreground">No aliases</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {element.alias_groups.map((ag) => (
                  <li key={ag.id}>
                    <Link
                      href={`/aliases/${ag.id}`}
                      className="text-blue-600 hover:underline"
                    >
                      {ag.name}
                    </Link>
                    <span className="text-muted-foreground">
                      {" "}
                      ({ag.member_count} members, {ag.sssom_predicate})
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Mappings as Input ({element.mappings_as_input.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {element.mappings_as_input.length === 0 ? (
              <p className="text-sm text-muted-foreground">None</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {element.mappings_as_input.map((m) => (
                  <li key={m.id}>
                    <Badge variant="outline" className="mr-1">
                      {m.function_type}
                    </Badge>
                    {m.output_name && (
                      <span className="text-muted-foreground">
                        &rarr; {m.output_name}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Mappings as Output ({element.mappings_as_output.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {element.mappings_as_output.length === 0 ? (
              <p className="text-sm text-muted-foreground">None</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {element.mappings_as_output.map((m) => (
                  <li key={m.id}>
                    <Badge variant="outline" className="mr-1">
                      {m.function_type}
                    </Badge>
                    {m.input_names && (
                      <span className="text-muted-foreground">
                        &larr; {m.input_names.join(", ")}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Relationship Graph</CardTitle>
        </CardHeader>
        <CardContent>
          <RelationshipGraph elementId={element.id} />
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span>{value}</span>
    </div>
  );
}

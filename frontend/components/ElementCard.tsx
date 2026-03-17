import { Badge } from "@/components/ui/badge";
import type { DataElement } from "@/lib/types";
import Link from "next/link";

interface ElementCardProps {
  element: DataElement;
}

const TYPE_COLORS: Record<string, string> = {
  string: "bg-blue-100 text-blue-800",
  integer: "bg-green-100 text-green-800",
  float: "bg-green-100 text-green-800",
  boolean: "bg-purple-100 text-purple-800",
  object: "bg-orange-100 text-orange-800",
  array: "bg-pink-100 text-pink-800",
};

export function ElementCard({ element }: ElementCardProps) {
  const name = element.provenance[0]?.name || "unknown";
  const description = element.provenance[0]?.description;
  const truncated =
    description && description.length > 120
      ? description.slice(0, 120) + "..."
      : description;

  const typeClass =
    TYPE_COLORS[element.semantic.data_type] || "bg-gray-100 text-gray-800";

  return (
    <Link
      href={`/elements/${encodeURIComponent(element.uri)}`}
      className="block rounded-md border p-4 transition-colors hover:bg-muted/50"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-medium">{name}</h3>
        <Badge variant="outline" className={typeClass}>
          {element.semantic.data_type}
        </Badge>
      </div>
      {truncated && (
        <p className="mt-1 text-sm text-muted-foreground">{truncated}</p>
      )}
      <div className="mt-2 flex gap-2">
        {element.provenance.map((p, i) => (
          <Badge key={`${p.source}-${i}`} variant="secondary">
            {p.source}
          </Badge>
        ))}
        {element.provenance.length > 1 && (
          <Badge variant="outline">
            {element.provenance.length} sources
          </Badge>
        )}
      </div>
    </Link>
  );
}

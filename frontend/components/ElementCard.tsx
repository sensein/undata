import { Badge } from "@/components/ui/badge";
import type { DataElementSummary } from "@/lib/types";
import Link from "next/link";

interface ElementCardProps {
  element: DataElementSummary;
}

const TYPE_COLORS: Record<string, string> = {
  string: "bg-blue-100 text-blue-800",
  number: "bg-green-100 text-green-800",
  boolean: "bg-purple-100 text-purple-800",
  object: "bg-orange-100 text-orange-800",
  array: "bg-pink-100 text-pink-800",
};

export function ElementCard({ element }: ElementCardProps) {
  const description =
    element.description && element.description.length > 120
      ? element.description.slice(0, 120) + "..."
      : element.description;

  const typeClass = TYPE_COLORS[element.data_type] || "bg-gray-100 text-gray-800";

  return (
    <Link
      href={`/elements/${element.id}`}
      className="block rounded-md border p-4 transition-colors hover:bg-muted/50"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-medium">{element.name}</h3>
        <Badge variant="outline" className={typeClass}>
          {element.data_type}
        </Badge>
      </div>
      {description && (
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      )}
      <div className="mt-2 flex gap-2">
        <Badge variant="secondary">{element.source.name}</Badge>
        {element.alias_count > 0 && (
          <Badge variant="outline">
            {element.alias_count} alias{element.alias_count !== 1 ? "es" : ""}
          </Badge>
        )}
      </div>
    </Link>
  );
}

import { Badge } from "@/components/ui/badge";
import type { PathwaySummary } from "@/lib/types";
import Link from "next/link";

interface PathwayCardProps {
  pathway: PathwaySummary;
}

export function PathwayCard({ pathway }: PathwayCardProps) {
  return (
    <Link
      href={`/migrations/${pathway.id}`}
      className="block rounded-md border p-4 transition-colors hover:bg-muted/50"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-medium">{pathway.source_schema.name}</span>
          <span className="text-muted-foreground">&rarr;</span>
          <span className="font-medium">{pathway.target_schema.name}</span>
        </div>
        <Badge variant="secondary">
          {pathway.step_count} step{pathway.step_count !== 1 ? "s" : ""}
        </Badge>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Created {new Date(pathway.created_at).toLocaleDateString()}
      </p>
    </Link>
  );
}

import { Badge } from "@/components/ui/badge";
import type { SchemaDiffResult } from "@/lib/types";

interface SchemaDiffProps {
  diff: SchemaDiffResult;
}

export function SchemaDiff({ diff }: SchemaDiffProps) {
  const hasChanges =
    diff.added.length > 0 || diff.removed.length > 0 || diff.modified.length > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Badge variant="secondary">{diff.schema_a.name}</Badge>
        <span className="text-muted-foreground">&rarr;</span>
        <Badge variant="secondary">{diff.schema_b.name}</Badge>
      </div>

      {!hasChanges && (
        <p className="text-sm text-muted-foreground">Schemas are identical.</p>
      )}

      {diff.added.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-green-700">
            Added ({diff.added.length})
          </h3>
          <ul className="space-y-1">
            {diff.added.map((field) => (
              <li
                key={field}
                className="rounded bg-green-50 px-3 py-1.5 text-sm"
                aria-label="added field"
              >
                + {field}
              </li>
            ))}
          </ul>
        </div>
      )}

      {diff.removed.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-red-700">
            Removed ({diff.removed.length})
          </h3>
          <ul className="space-y-1">
            {diff.removed.map((field) => (
              <li
                key={field}
                className="rounded bg-red-50 px-3 py-1.5 text-sm"
                aria-label="removed field"
              >
                - {field}
              </li>
            ))}
          </ul>
        </div>
      )}

      {diff.modified.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-medium text-amber-700">
            Modified ({diff.modified.length})
          </h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2">Field</th>
                <th className="py-2">Old Type</th>
                <th className="py-2">New Type</th>
              </tr>
            </thead>
            <tbody>
              {diff.modified.map((m) => (
                <tr key={m.field} className="border-b" aria-label="modified field">
                  <td className="py-2">{m.field}</td>
                  <td className="py-2 text-red-600">{m.old_type}</td>
                  <td className="py-2 text-green-600">{m.new_type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

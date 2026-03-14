"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorBanner } from "@/components/ErrorBanner";
import { registerAlias } from "@/lib/api/aliases";
import type { DataElementDetail } from "@/lib/types";
import { useMutation } from "@tanstack/react-query";

interface ComparisonViewProps {
  elementA: DataElementDetail;
  elementB: DataElementDetail;
}

const COMPARE_FIELDS: Array<{
  key: keyof DataElementDetail;
  label: string;
}> = [
  { key: "name", label: "Name" },
  { key: "data_type", label: "Data Type" },
  { key: "description", label: "Description" },
  { key: "required", label: "Required" },
  { key: "multivalued", label: "Multivalued" },
  { key: "version_num", label: "Version" },
];

function formatValue(val: unknown): string {
  if (val == null) return "-";
  if (typeof val === "boolean") return val ? "Yes" : "No";
  if (Array.isArray(val)) return val.join(", ") || "-";
  return String(val);
}

export function ComparisonView({ elementA, elementB }: ComparisonViewProps) {
  const typesMatch = elementA.data_type === elementB.data_type;

  const aliasMutation = useMutation({
    mutationFn: () => registerAlias(elementA.id, elementB.id),
  });

  return (
    <div className="space-y-6">
      {aliasMutation.error && (
        <ErrorBanner error={aliasMutation.error as Error} />
      )}
      {aliasMutation.isSuccess && (
        <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-800">
          Alias registered successfully.
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left">
              <th className="py-3 pr-4 font-medium text-muted-foreground">
                Field
              </th>
              <th className="py-3 pr-4 font-medium">{elementA.name}</th>
              <th className="py-3 pr-4 font-medium">{elementB.name}</th>
              <th className="py-3 font-medium">Match</th>
            </tr>
          </thead>
          <tbody>
            {COMPARE_FIELDS.map(({ key, label }) => {
              const valA = formatValue(elementA[key]);
              const valB = formatValue(elementB[key]);
              const isMatch = valA === valB;

              return (
                <tr key={key} className="border-b">
                  <td className="py-3 pr-4 text-muted-foreground">{label}</td>
                  <td
                    className={`py-3 pr-4 ${!isMatch ? "bg-amber-50" : ""}`}
                    aria-label={isMatch ? "matching" : "differs"}
                  >
                    {valA}
                  </td>
                  <td
                    className={`py-3 pr-4 ${!isMatch ? "bg-amber-50" : ""}`}
                    aria-label={isMatch ? "matching" : "differs"}
                  >
                    {valB}
                  </td>
                  <td className="py-3">
                    {isMatch ? (
                      <span className="text-green-600" aria-label="matching">
                        ✓
                      </span>
                    ) : (
                      <span className="text-amber-600" aria-label="differs">
                        ≠
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
            <tr className="border-b">
              <td className="py-3 pr-4 text-muted-foreground">Source</td>
              <td className="py-3 pr-4">
                <Badge variant="secondary">{elementA.source.name}</Badge>
              </td>
              <td className="py-3 pr-4">
                <Badge variant="secondary">{elementB.source.name}</Badge>
              </td>
              <td className="py-3">
                {elementA.source.name === elementB.source.name ? (
                  <span className="text-green-600" aria-label="matching">
                    ✓
                  </span>
                ) : (
                  <span className="text-amber-600" aria-label="differs">
                    ≠
                  </span>
                )}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <Button
        onClick={() => aliasMutation.mutate()}
        disabled={!typesMatch || aliasMutation.isPending || aliasMutation.isSuccess}
      >
        {aliasMutation.isPending
          ? "Registering..."
          : aliasMutation.isSuccess
            ? "Alias Registered"
            : "Register as Alias"}
      </Button>
      {!typesMatch && (
        <p className="text-sm text-muted-foreground">
          Data types must match to register as alias.
        </p>
      )}
    </div>
  );
}

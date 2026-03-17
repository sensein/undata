"use client";

import { Badge } from "@/components/ui/badge";
import { ErrorBanner } from "@/components/ErrorBanner";
import type { DataElement } from "@/lib/types";

interface ComparisonViewProps {
  elementA: DataElement;
  elementB: DataElement;
}

interface CompareRow {
  label: string;
  valueA: string;
  valueB: string;
}

function getRows(a: DataElement, b: DataElement): CompareRow[] {
  const nameA = a.provenance[0]?.name || "-";
  const nameB = b.provenance[0]?.name || "-";
  return [
    { label: "Name", valueA: nameA, valueB: nameB },
    { label: "Data Type", valueA: a.semantic.data_type, valueB: b.semantic.data_type },
    { label: "Unit", valueA: a.semantic.unit || "-", valueB: b.semantic.unit || "-" },
    { label: "Ontology", valueA: a.semantic.ontology_term || "-", valueB: b.semantic.ontology_term || "-" },
    { label: "Sources", valueA: a.provenance.map((p) => p.source).join(", "), valueB: b.provenance.map((p) => p.source).join(", ") },
  ];
}

export function ComparisonView({ elementA, elementB }: ComparisonViewProps) {
  const rows = getRows(elementA, elementB);
  const nameA = elementA.provenance[0]?.name || "Element A";
  const nameB = elementB.provenance[0]?.name || "Element B";
  const hashMatch = elementA.uri === elementB.uri;

  return (
    <div className="space-y-6">
      {hashMatch && (
        <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-800">
          These elements have the same content hash — they are the same semantic concept.
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left">
              <th className="py-3 pr-4 font-medium text-muted-foreground">Field</th>
              <th className="py-3 pr-4 font-medium">{nameA}</th>
              <th className="py-3 pr-4 font-medium">{nameB}</th>
              <th className="py-3 font-medium">Match</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ label, valueA, valueB }) => {
              const isMatch = valueA === valueB;
              return (
                <tr key={label} className="border-b">
                  <td className="py-3 pr-4 text-muted-foreground">{label}</td>
                  <td className={`py-3 pr-4 ${!isMatch ? "bg-amber-50" : ""}`} aria-label={isMatch ? "matching" : "differs"}>
                    {valueA}
                  </td>
                  <td className={`py-3 pr-4 ${!isMatch ? "bg-amber-50" : ""}`} aria-label={isMatch ? "matching" : "differs"}>
                    {valueB}
                  </td>
                  <td className="py-3">
                    {isMatch ? (
                      <span className="text-green-600" aria-label="matching">✓</span>
                    ) : (
                      <span className="text-amber-600" aria-label="differs">≠</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

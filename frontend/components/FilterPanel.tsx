"use client";

import { Label } from "@/components/ui/label";
import type { FilterState } from "@/lib/types";
import { useQuery } from "@tanstack/react-query";
import { getSources } from "@/lib/api/sources";

interface FilterPanelProps {
  filters: FilterState;
  onFilterChange: (filters: FilterState) => void;
}

const DATA_TYPES = ["string", "number", "boolean", "object", "array"];

export function FilterPanel({ filters, onFilterChange }: FilterPanelProps) {
  const { data: sources } = useQuery({
    queryKey: ["sources"],
    queryFn: getSources,
  });

  return (
    <div className="space-y-4">
      <div>
        <Label htmlFor="source-filter">Source Schema</Label>
        <select
          id="source-filter"
          className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
          value={filters.source_id || ""}
          onChange={(e) =>
            onFilterChange({ ...filters, source_id: e.target.value || null })
          }
        >
          <option value="">All sources</option>
          {sources?.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <Label htmlFor="type-filter">Data Type</Label>
        <select
          id="type-filter"
          className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
          value={filters.data_type || ""}
          onChange={(e) =>
            onFilterChange({ ...filters, data_type: e.target.value || null })
          }
        >
          <option value="">All types</option>
          {DATA_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      <div className="flex items-center gap-2">
        <input
          id="has-aliases"
          type="checkbox"
          checked={filters.has_aliases === true}
          onChange={(e) =>
            onFilterChange({
              ...filters,
              has_aliases: e.target.checked ? true : null,
            })
          }
        />
        <Label htmlFor="has-aliases">Has aliases</Label>
      </div>

      <div className="flex items-center gap-2">
        <input
          id="has-mappings"
          type="checkbox"
          checked={filters.has_mappings === true}
          onChange={(e) =>
            onFilterChange({
              ...filters,
              has_mappings: e.target.checked ? true : null,
            })
          }
        />
        <Label htmlFor="has-mappings">Has mappings</Label>
      </div>
    </div>
  );
}

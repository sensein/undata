"use client";

import { useState, useMemo } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
  type ColumnFiltersState,
} from "@tanstack/react-table";

interface EntityDataGridProps<T> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  columns: ColumnDef<T, any>[];
  data: T[];
  isLoading?: boolean;
  totalCount?: number;
  onLoadMore?: () => void;
  hasNextPage?: boolean;
}

export function EntityDataGrid<T>({
  columns,
  data,
  isLoading = false,
  totalCount,
  onLoadMore,
  hasNextPage,
}: EntityDataGridProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);

  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data,
    columns,
    state: { sorting, columnFilters },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    sortingFns: {
      caseInsensitive: (rowA, rowB, columnId) => {
        const a = String(rowA.getValue(columnId) ?? "").toLowerCase();
        const b = String(rowB.getValue(columnId) ?? "").toLowerCase();
        return a.localeCompare(b);
      },
    },
  });

  // Loading skeleton
  if (isLoading && data.length === 0) {
    return (
      <div className="space-y-2">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div>
      {/* Count */}
      {totalCount != null && (
        <div className="text-xs text-gray-500 mb-2">{totalCount} total</div>
      )}

      {/* Table */}
      <div className="overflow-x-auto border rounded-lg">
        <table className="w-full text-sm">
          {/* Header row 1: column names (sortable) */}
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} className="bg-gray-50 border-b">
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className={`text-left px-2 py-1.5 font-medium text-xs text-gray-700 ${
                      header.column.getCanSort() ? "cursor-pointer select-none hover:bg-gray-100" : ""
                    }`}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getIsSorted() === "asc" && <span className="text-blue-500">↑</span>}
                      {header.column.getIsSorted() === "desc" && <span className="text-blue-500">↓</span>}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
            {/* Header row 2: per-column filters */}
            <tr className="border-b bg-gray-50/50">
              {table.getHeaderGroups()[0]?.headers.map((header) => (
                <th key={`filter-${header.id}`} className="p-2">
                  {header.column.getCanFilter() && (
                    <input
                      type="text"
                      value={(header.column.getFilterValue() as string) ?? ""}
                      onChange={(e) => header.column.setFilterValue(e.target.value || undefined)}
                      placeholder="Filter..."
                      className="w-full px-2 py-1 text-xs border rounded bg-white"
                    />
                  )}
                </th>
              ))}
            </tr>
          </thead>

          {/* Body */}
          <tbody>
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="p-8 text-center text-gray-500">
                  No results found.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="border-b hover:bg-gray-50 transition-colors">
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-2 py-1">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Load more */}
      {hasNextPage && onLoadMore && (
        <button
          onClick={onLoadMore}
          className="mt-4 w-full py-2 text-sm text-blue-600 border rounded hover:bg-blue-50 transition-colors"
        >
          Load more
        </button>
      )}
    </div>
  );
}

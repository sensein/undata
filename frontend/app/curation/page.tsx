"use client";

import { useState } from "react";

// Curation page — reads flags from the GraphQL API
// For now, a placeholder that shows the curation workflow concept

export default function CurationPage() {
  const [statusFilter, setStatusFilter] = useState("pending");

  return (
    <div className="max-w-7xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Curation Queue</h1>

      <div className="flex gap-4 mb-6">
        <select
          className="border rounded px-3 py-2"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="deferred">Deferred</option>
        </select>
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded p-4 text-sm">
        <p className="font-medium">Curation queue requires GraphQL mutations</p>
        <p className="text-gray-600 mt-1">
          The curation workflow (approve/reject/defer flags) needs mutation resolvers
          in the GraphQL backend. Use the CLI for now:
        </p>
        <pre className="mt-2 bg-white p-3 rounded text-xs font-mono">
          undata-library curation-queue /path/to/registry --status pending{"\n"}
          undata-library resolve-flag /path/to/registry --id FLAG_ID --action approved --by curator@example.com
        </pre>
      </div>
    </div>
  );
}

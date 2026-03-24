"use client";

import { useState } from "react";

interface FlagResolverProps {
  flagId: string;
  flagType: string;
  entityRef: string;
  context: { reason?: string; [key: string]: unknown };
  onResolved?: () => void;
}

export function FlagResolver({
  flagId,
  flagType,
  entityRef,
  context,
  onResolved,
}: FlagResolverProps) {
  const [action, setAction] = useState<"approved" | "rejected" | "deferred">(
    "approved"
  );
  const [note, setNote] = useState("");

  const handleResolve = () => {
    // TODO: Call GraphQL mutation when implemented
    // For now, log to console
    console.log("Resolve flag:", { flagId, action, note });
    onResolved?.();
  };

  return (
    <div className="border rounded p-4">
      <div className="flex justify-between items-start mb-3">
        <div>
          <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-xs">
            {flagType}
          </span>
          <span className="ml-2 text-sm font-mono">{entityRef}</span>
        </div>
        <span className="text-xs text-gray-500">{flagId.slice(0, 12)}</span>
      </div>

      {context.reason != null ? (
        <p className="text-sm text-gray-600 mb-3">
          {String(context.reason)}
        </p>
      ) : null}

      <div className="flex gap-2 items-end">
        <select
          className="border rounded px-2 py-1 text-sm"
          value={action}
          onChange={(e) =>
            setAction(
              e.target.value as "approved" | "rejected" | "deferred"
            )
          }
        >
          <option value="approved">Approve</option>
          <option value="rejected">Reject</option>
          <option value="deferred">Defer</option>
        </select>
        <input
          type="text"
          className="flex-1 border rounded px-2 py-1 text-sm"
          placeholder="Resolution note..."
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <button
          className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
          onClick={handleResolve}
        >
          Resolve
        </button>
      </div>
    </div>
  );
}

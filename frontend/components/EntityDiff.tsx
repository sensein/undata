"use client";

interface DiffEntry {
  field: string;
  old_value: unknown;
  new_value: unknown;
}

interface EntityDiffProps {
  diffs: DiffEntry[];
  onApply?: (diff: DiffEntry) => void;
  onDiscard?: (diff: DiffEntry) => void;
  onApplyAll?: () => void;
  onDiscardAll?: () => void;
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v, null, 2);
  return String(v);
}

export function EntityDiff({ diffs, onApply, onDiscard, onApplyAll, onDiscardAll }: EntityDiffProps) {
  if (diffs.length === 0) {
    return <p className="text-sm text-gray-400 p-4">No pending changes.</p>;
  }

  return (
    <div className="space-y-3 p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-sm">{diffs.length} pending change{diffs.length !== 1 ? "s" : ""}</h3>
        <div className="flex gap-2">
          {onApplyAll && (
            <button onClick={onApplyAll} className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700">
              Apply All
            </button>
          )}
          {onDiscardAll && (
            <button onClick={onDiscardAll} className="px-3 py-1 bg-gray-400 text-white text-xs rounded hover:bg-gray-500">
              Discard All
            </button>
          )}
        </div>
      </div>

      {diffs.map((diff, i) => (
        <div key={i} className="border rounded p-3 text-sm">
          <div className="font-mono font-medium text-gray-700 mb-1">{diff.field}</div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <span className="text-xs text-gray-500 uppercase">Before</span>
              <div className="bg-red-50 text-red-800 p-1 rounded text-xs font-mono whitespace-pre-wrap break-all">
                {formatValue(diff.old_value)}
              </div>
            </div>
            <div>
              <span className="text-xs text-gray-500 uppercase">After</span>
              <div className="bg-green-50 text-green-800 p-1 rounded text-xs font-mono whitespace-pre-wrap break-all">
                {formatValue(diff.new_value)}
              </div>
            </div>
          </div>
          {(onApply || onDiscard) && (
            <div className="flex gap-2 mt-2">
              {onApply && (
                <button onClick={() => onApply(diff)} className="text-xs text-green-600 hover:underline">Apply</button>
              )}
              {onDiscard && (
                <button onClick={() => onDiscard(diff)} className="text-xs text-gray-500 hover:underline">Discard</button>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

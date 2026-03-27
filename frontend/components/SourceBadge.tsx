import { getSourceColor } from "@/lib/source-colors";

export function SourceBadge({ source }: { source: string }) {
  const { bg, text } = getSourceColor(source);
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${bg} ${text}`}>
      {source}
    </span>
  );
}

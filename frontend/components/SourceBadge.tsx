import Link from "next/link";
import { getSourceColor } from "@/lib/source-colors";

export function SourceBadge({ source }: { source: string }) {
  const { bg, text } = getSourceColor(source);
  return (
    <Link
      href={`/sources/${encodeURIComponent(source)}`}
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${bg} ${text} hover:opacity-80 transition-opacity`}
    >
      {source}
    </Link>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { getSourceColor } from "@/lib/source-colors";

export function SourceBadge({ source, linkable = true }: { source: string; linkable?: boolean }) {
  const { bg, text } = getSourceColor(source);
  const router = useRouter();

  const className = `inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${bg} ${text} ${linkable ? "cursor-pointer hover:opacity-80" : ""} transition-opacity`;

  if (linkable) {
    return (
      <span
        className={className}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          router.push(`/sources/${encodeURIComponent(source)}`);
        }}
        role="link"
        tabIndex={0}
      >
        {source}
      </span>
    );
  }

  return <span className={className}>{source}</span>;
}

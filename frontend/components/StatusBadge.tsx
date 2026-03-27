import { getStatusColor } from "@/lib/source-colors";

const ICONS: Record<string, string> = {
  check: "✓",
  x: "✗",
  exclamation: "!",
  minus: "—",
};

export function StatusBadge({ status }: { status: string }) {
  const { bg, text, icon } = getStatusColor(status);
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${bg} ${text}`}>
      <span>{ICONS[icon] ?? ""}</span>
      {status}
    </span>
  );
}

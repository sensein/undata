/**
 * Centralized color maps for sources and entity types.
 * Used by SourceBadge, EntityTag, and all browse/detail pages.
 */

// Source → Tailwind bg + text classes
const SOURCE_COLORS: Record<string, { bg: string; text: string }> = {
  bids: { bg: "bg-blue-100", text: "text-blue-800" },
  dandi: { bg: "bg-green-100", text: "text-green-800" },
  nwb: { bg: "bg-purple-100", text: "text-purple-800" },
  openminds: { bg: "bg-orange-100", text: "text-orange-800" },
  aind: { bg: "bg-teal-100", text: "text-teal-800" },
  reproschema: { bg: "bg-rose-100", text: "text-rose-800" },
  nda: { bg: "bg-indigo-100", text: "text-indigo-800" },
  openneuro: { bg: "bg-amber-100", text: "text-amber-800" },
};

const DEFAULT_SOURCE_COLOR = { bg: "bg-gray-100", text: "text-gray-800" };

// Entity type → Tailwind bg + text classes
const ENTITY_TYPE_COLORS: Record<string, { bg: string; text: string }> = {
  element: { bg: "bg-cyan-100", text: "text-cyan-800" },
  elements: { bg: "bg-cyan-100", text: "text-cyan-800" },
  schema: { bg: "bg-blue-100", text: "text-blue-800" },
  schemas: { bg: "bg-blue-100", text: "text-blue-800" },
  value: { bg: "bg-lime-100", text: "text-lime-800" },
  values: { bg: "bg-lime-100", text: "text-lime-800" },
  valueset: { bg: "bg-green-100", text: "text-green-800" },
  valuesets: { bg: "bg-green-100", text: "text-green-800" },
  transform: { bg: "bg-amber-100", text: "text-amber-800" },
  transforms: { bg: "bg-amber-100", text: "text-amber-800" },
  flag: { bg: "bg-red-100", text: "text-red-800" },
  contribution: { bg: "bg-yellow-100", text: "text-yellow-800" },
};

const DEFAULT_ENTITY_COLOR = { bg: "bg-gray-100", text: "text-gray-800" };

// Status → Tailwind classes + icon hint
export const STATUS_COLORS: Record<
  string,
  { bg: string; text: string; icon: string }
> = {
  pending: {
    bg: "bg-yellow-100",
    text: "text-yellow-800",
    icon: "exclamation",
  },
  approved: { bg: "bg-green-100", text: "text-green-800", icon: "check" },
  rejected: { bg: "bg-red-100", text: "text-red-800", icon: "x" },
  deferred: { bg: "bg-gray-100", text: "text-gray-600", icon: "minus" },
};

export function getSourceColor(source: string): { bg: string; text: string } {
  const key = source.toLowerCase();
  // Exact match first, then prefix match (e.g., "openneuro/ds007615" → "openneuro")
  return SOURCE_COLORS[key] ?? SOURCE_COLORS[key.split("/")[0]] ?? DEFAULT_SOURCE_COLOR;
}

export function getEntityColor(
  entityType: string,
): { bg: string; text: string } {
  return ENTITY_TYPE_COLORS[entityType.toLowerCase()] ?? DEFAULT_ENTITY_COLOR;
}

export function getStatusColor(
  status: string,
): { bg: string; text: string; icon: string } {
  return (
    STATUS_COLORS[status.toLowerCase()] ?? {
      bg: "bg-gray-100",
      text: "text-gray-600",
      icon: "minus",
    }
  );
}

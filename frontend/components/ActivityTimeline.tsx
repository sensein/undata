import { getStatusColor, getEntityColor } from "@/lib/source-colors";

interface ActivityEvent {
  type: string; // flag_created, flag_resolved, contribution
  entityRef: string;
  entityType?: string;
  timestamp: string;
  description?: string;
  status?: string;
}

interface ActivityTimelineProps {
  events: ActivityEvent[];
  onLoadMore?: () => void;
  hasMore?: boolean;
}

const TYPE_LABELS: Record<string, string> = {
  flag_created: "Flag Created",
  flag_resolved: "Flag Resolved",
  contribution: "Contribution",
};

export function ActivityTimeline({ events, onLoadMore, hasMore }: ActivityTimelineProps) {
  if (events.length === 0) {
    return <p className="text-gray-500 text-center py-8">No activity yet.</p>;
  }

  return (
    <div className="space-y-0">
      {events.map((event, i) => {
        const typeLabel = TYPE_LABELS[event.type] ?? event.type;
        const { bg, text } = event.type.includes("flag")
          ? getStatusColor(event.status ?? "pending")
          : getEntityColor(event.entityType ?? "contribution");

        return (
          <div key={i} className="flex gap-4 py-3 border-b last:border-b-0">
            {/* Timeline dot */}
            <div className="flex flex-col items-center">
              <div className={`w-3 h-3 rounded-full ${bg} border-2 border-white shadow`} />
              {i < events.length - 1 && <div className="w-px flex-1 bg-gray-200" />}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${bg} ${text}`}>
                  {typeLabel}
                </span>
                <span className="text-sm font-mono text-gray-600 truncate">{event.entityRef}</span>
              </div>
              {event.description && (
                <p className="text-sm text-gray-500">{event.description}</p>
              )}
              <time className="text-xs text-gray-400">{event.timestamp}</time>
            </div>
          </div>
        );
      })}

      {hasMore && onLoadMore && (
        <button
          onClick={onLoadMore}
          className="w-full py-2 text-sm text-blue-600 hover:text-blue-800"
        >
          Load older
        </button>
      )}
    </div>
  );
}

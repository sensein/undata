import { ApiError } from "@/lib/api/client";

interface ErrorBannerProps {
  error: Error | ApiError | null;
}

export function ErrorBanner({ error }: ErrorBannerProps) {
  if (!error) return null;

  const isServiceUnavailable =
    error instanceof ApiError && error.status === 503;

  return (
    <div
      role="alert"
      className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800"
    >
      {isServiceUnavailable
        ? "Service unavailable. Please try again later."
        : error.message || "An unexpected error occurred."}
    </div>
  );
}

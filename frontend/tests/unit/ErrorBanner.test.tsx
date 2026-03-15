import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ApiError } from "@/lib/api/client";

describe("ErrorBanner", () => {
  it("renders nothing when error is null", () => {
    const { container } = render(<ErrorBanner error={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders "Service unavailable" on 503 ApiError', () => {
    const error = new ApiError(503, "backend down");
    render(<ErrorBanner error={error} />);
    expect(
      screen.getByText("Service unavailable. Please try again later."),
    ).toBeInTheDocument();
  });

  it("renders error detail text on non-503 ApiError", () => {
    const error = new ApiError(422, "Validation failed");
    render(<ErrorBanner error={error} />);
    expect(screen.getByText("Validation failed")).toBeInTheDocument();
  });

  it("renders generic message for plain Error", () => {
    const error = new Error("Something broke");
    render(<ErrorBanner error={error} />);
    expect(screen.getByText("Something broke")).toBeInTheDocument();
  });

  it("has alert role for accessibility", () => {
    const error = new ApiError(500, "Server error");
    render(<ErrorBanner error={error} />);
    const alerts = screen.getAllByRole("alert");
    expect(alerts.length).toBeGreaterThanOrEqual(1);
  });
});

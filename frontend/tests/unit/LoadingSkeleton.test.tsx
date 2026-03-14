import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { LoadingSkeleton } from "@/components/LoadingSkeleton";

describe("LoadingSkeleton", () => {
  afterEach(() => cleanup());

  it("renders 5 skeleton rows by default", () => {
    render(<LoadingSkeleton />);
    const container = screen.getByLabelText("Loading");
    const rows = container.querySelectorAll(":scope > div");
    expect(rows.length).toBe(5);
  });

  it("renders the specified number of rows", () => {
    render(<LoadingSkeleton count={3} />);
    const container = screen.getByLabelText("Loading");
    const rows = container.querySelectorAll(":scope > div");
    expect(rows.length).toBe(3);
  });

  it("has loading status role and aria-label", () => {
    render(<LoadingSkeleton />);
    const container = screen.getByLabelText("Loading");
    expect(container).toHaveAttribute("role", "status");
  });
});

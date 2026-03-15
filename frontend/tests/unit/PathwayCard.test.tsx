import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PathwayCard } from "@/components/PathwayCard";
import type { PathwaySummary } from "@/lib/types";

const mockPathway: PathwaySummary = {
  id: "pw-1",
  source_schema: { id: "s1", name: "BIDS v1.8" },
  target_schema: { id: "s2", name: "NWB 2.7" },
  step_count: 3,
  created_at: "2026-03-10T10:00:00Z",
};

describe("PathwayCard", () => {
  afterEach(() => cleanup());

  it("renders source and target schema names", () => {
    render(<PathwayCard pathway={mockPathway} />);
    expect(screen.getByText("BIDS v1.8")).toBeInTheDocument();
    expect(screen.getByText("NWB 2.7")).toBeInTheDocument();
  });

  it("renders step count", () => {
    render(<PathwayCard pathway={mockPathway} />);
    expect(screen.getByText("3 steps")).toBeInTheDocument();
  });

  it("renders singular step for count=1", () => {
    const single = { ...mockPathway, step_count: 1 };
    render(<PathwayCard pathway={single} />);
    expect(screen.getByText("1 step")).toBeInTheDocument();
  });

  it("links to pathway detail page", () => {
    render(<PathwayCard pathway={mockPathway} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/migrations/pw-1");
  });

  it("renders creation date", () => {
    render(<PathwayCard pathway={mockPathway} />);
    expect(screen.getByText(/Created/)).toBeInTheDocument();
  });
});

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ElementCard } from "@/components/ElementCard";
import type { DataElementSummary } from "@/lib/types";

const mockElement: DataElementSummary = {
  id: "abc-123",
  name: "subject_age",
  data_type: "number",
  description: "Age of the participant at the time of data acquisition",
  required: true,
  multivalued: false,
  source: { id: "src-1", name: "BIDS" },
  alias_count: 2,
  mapping_count: 1,
  version_num: 1,
};

describe("ElementCard", () => {
  afterEach(() => cleanup());

  it("renders element name", () => {
    render(<ElementCard element={mockElement} />);
    expect(screen.getByText("subject_age")).toBeInTheDocument();
  });

  it("renders data type badge", () => {
    render(<ElementCard element={mockElement} />);
    expect(screen.getByText("number")).toBeInTheDocument();
  });

  it("renders source badge", () => {
    render(<ElementCard element={mockElement} />);
    expect(screen.getByText("BIDS")).toBeInTheDocument();
  });

  it("renders alias count", () => {
    render(<ElementCard element={mockElement} />);
    expect(screen.getByText("2 aliases")).toBeInTheDocument();
  });

  it("truncates long descriptions to 120 chars", () => {
    const longDesc = "A".repeat(200);
    const el = { ...mockElement, description: longDesc };
    render(<ElementCard element={el} />);
    const desc = screen.getByText(/A{120}\.\.\./);
    expect(desc).toBeInTheDocument();
  });

  it("links to element detail page", () => {
    render(<ElementCard element={mockElement} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/elements/abc-123");
  });
});

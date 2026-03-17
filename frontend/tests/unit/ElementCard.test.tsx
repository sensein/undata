import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ElementCard } from "@/components/ElementCard";
import type { DataElement } from "@/lib/types";

const mockElement: DataElement = {
  uri: "https://schema.undata.live/elements/age_x7k2m9",
  semantic: {
    ontology_term: "http://purl.obolibrary.org/obo/NCIT_C25150",
    data_type: "float",
    unit: "year",
    constraints: null,
  },
  provenance: [
    {
      source: "bids",
      class: "Participant",
      name: "subject_age",
      description: "Age of the participant at the time of data acquisition",
      required: true,
      multivalued: null,
    },
    {
      source: "nwb",
      class: "Subject",
      name: "age",
      description: "Subject age",
      required: null,
      multivalued: null,
    },
  ],
};

describe("ElementCard", () => {
  afterEach(() => cleanup());

  it("renders element name from first provenance", () => {
    render(<ElementCard element={mockElement} />);
    expect(screen.getByText("subject_age")).toBeInTheDocument();
  });

  it("renders data type badge", () => {
    render(<ElementCard element={mockElement} />);
    expect(screen.getByText("float")).toBeInTheDocument();
  });

  it("renders source badges", () => {
    render(<ElementCard element={mockElement} />);
    expect(screen.getByText("bids")).toBeInTheDocument();
    expect(screen.getByText("nwb")).toBeInTheDocument();
  });

  it("renders multi-source count", () => {
    render(<ElementCard element={mockElement} />);
    expect(screen.getByText("2 sources")).toBeInTheDocument();
  });

  it("truncates long descriptions to 120 chars", () => {
    const longDesc = "A".repeat(200);
    const el: DataElement = {
      ...mockElement,
      provenance: [{ ...mockElement.provenance[0], description: longDesc }],
    };
    render(<ElementCard element={el} />);
    const desc = screen.getByText(/A{120}\.\.\./);
    expect(desc).toBeInTheDocument();
  });

  it("links to element detail page with encoded URI", () => {
    render(<ElementCard element={mockElement} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute(
      "href",
      `/elements/${encodeURIComponent(mockElement.uri)}`,
    );
  });
});

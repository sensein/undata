import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { RelationshipGraph } from "@/components/RelationshipGraph";
import type { DataElement } from "@/lib/types";

const mockElement: DataElement = {
  uri: "https://schema.undata.live/elements/age_x7k2m9",
  semantic: { ontology_term: "http://example.org/age", data_type: "float", unit: "year", constraints: null },
  provenance: [
    { source: "bids", class: "Participant", name: "age", description: "Age", required: true, multivalued: null },
    { source: "nwb", class: "Subject", name: "age", description: "Subject age", required: null, multivalued: null },
  ],
};

describe("RelationshipGraph", () => {
  afterEach(() => cleanup());

  it("renders element name", () => {
    render(<RelationshipGraph element={mockElement} />);
    expect(screen.getByText("age")).toBeInTheDocument();
  });

  it("renders data type", () => {
    render(<RelationshipGraph element={mockElement} />);
    expect(screen.getByText("float")).toBeInTheDocument();
  });

  it("renders provenance sources", () => {
    render(<RelationshipGraph element={mockElement} />);
    expect(screen.getByText("bids")).toBeInTheDocument();
    expect(screen.getByText("nwb")).toBeInTheDocument();
  });

  it("renders class.name for each provenance", () => {
    render(<RelationshipGraph element={mockElement} />);
    expect(screen.getByText("Participant.age")).toBeInTheDocument();
    expect(screen.getByText("Subject.age")).toBeInTheDocument();
  });
});

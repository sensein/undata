import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ElementDetail } from "@/components/ElementDetail";
import type { DataElement } from "@/lib/types";

const mockElement: DataElement = {
  uri: "https://schema.undata.live/elements/age_x7k2m9",
  semantic: {
    ontology_term: "http://purl.obolibrary.org/obo/NCIT_C25150",
    data_type: "float",
    unit: "year",
    constraints: { minimum: 0, maximum: 150 },
  },
  provenance: [
    { source: "bids", class: "Participant", name: "age", description: "Age in years", required: true, multivalued: null },
    { source: "nwb", class: "Subject", name: "age", description: "Subject age", required: null, multivalued: null },
  ],
};

describe("ElementDetail", () => {
  afterEach(() => cleanup());

  it("renders attribute name from first provenance", () => {
    render(<ElementDetail element={mockElement} />);
    expect(screen.getByText("age")).toBeInTheDocument();
  });

  it("renders URI", () => {
    render(<ElementDetail element={mockElement} />);
    expect(screen.getByText(mockElement.uri)).toBeInTheDocument();
  });

  it("renders data type badge", () => {
    render(<ElementDetail element={mockElement} />);
    expect(screen.getByText("float")).toBeInTheDocument();
  });

  it("renders ontology term", () => {
    render(<ElementDetail element={mockElement} />);
    expect(screen.getByText(mockElement.semantic.ontology_term!)).toBeInTheDocument();
  });

  it("renders unit", () => {
    render(<ElementDetail element={mockElement} />);
    expect(screen.getByText("year")).toBeInTheDocument();
  });

  it("renders multi-source badge", () => {
    render(<ElementDetail element={mockElement} />);
    expect(screen.getByText("2 sources")).toBeInTheDocument();
  });

  it("renders provenance entries", () => {
    render(<ElementDetail element={mockElement} />);
    expect(screen.getByText("bids")).toBeInTheDocument();
    expect(screen.getByText("nwb")).toBeInTheDocument();
  });
});

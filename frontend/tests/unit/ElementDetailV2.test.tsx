import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ElementDetailV2 } from "@/components/ElementDetailV2";
import type { ElementV2 } from "@/lib/types";

const mockElement: ElementV2 = {
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

describe("ElementDetailV2", () => {
  afterEach(() => cleanup());

  it("renders attribute name from first provenance", () => {
    render(<ElementDetailV2 element={mockElement} />);
    expect(screen.getByText("age")).toBeInTheDocument();
  });

  it("renders URI", () => {
    render(<ElementDetailV2 element={mockElement} />);
    expect(screen.getByText(mockElement.uri)).toBeInTheDocument();
  });

  it("renders data type badge", () => {
    render(<ElementDetailV2 element={mockElement} />);
    expect(screen.getByText("float")).toBeInTheDocument();
  });

  it("renders ontology term", () => {
    render(<ElementDetailV2 element={mockElement} />);
    expect(screen.getByText(mockElement.semantic.ontology_term!)).toBeInTheDocument();
  });

  it("renders unit", () => {
    render(<ElementDetailV2 element={mockElement} />);
    expect(screen.getByText("year")).toBeInTheDocument();
  });

  it("renders multi-source badge", () => {
    render(<ElementDetailV2 element={mockElement} />);
    expect(screen.getByText("2 sources")).toBeInTheDocument();
  });

  it("renders provenance entries", () => {
    render(<ElementDetailV2 element={mockElement} />);
    expect(screen.getByText("bids")).toBeInTheDocument();
    expect(screen.getByText("nwb")).toBeInTheDocument();
  });
});

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ValueConceptCard } from "@/components/ValueConceptCard";
import type { ValueConceptResponse } from "@/lib/types";

const mockValue: ValueConceptResponse = {
  uri: "https://schema.undata.live/values/male_p8k3n2",
  semantic: {
    ontology_term: "http://purl.obolibrary.org/obo/PATO_0000384",
    value_type: "categorical",
    label: "male",
  },
  provenance: [
    { source: "bids", raw_value: "male" },
    { source: "aind", raw_value: "Male" },
    { source: "nwb", raw_value: "M" },
  ],
};

describe("ValueConceptCard", () => {
  afterEach(() => cleanup());

  it("renders label", () => {
    render(<ValueConceptCard value={mockValue} />);
    expect(screen.getByText("male")).toBeInTheDocument();
  });

  it("renders ontology term", () => {
    render(<ValueConceptCard value={mockValue} />);
    expect(screen.getByText(mockValue.semantic.ontology_term!)).toBeInTheDocument();
  });

  it("renders source count badge", () => {
    render(<ValueConceptCard value={mockValue} />);
    expect(screen.getByText("3 sources")).toBeInTheDocument();
  });

  it("renders raw values per source", () => {
    render(<ValueConceptCard value={mockValue} />);
    expect(screen.getByText(/bids: "male"/)).toBeInTheDocument();
    expect(screen.getByText(/aind: "Male"/)).toBeInTheDocument();
    expect(screen.getByText(/nwb: "M"/)).toBeInTheDocument();
  });
});

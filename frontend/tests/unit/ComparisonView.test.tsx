import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ComparisonView } from "@/components/ComparisonView";
import type { DataElement } from "@/lib/types";

const baseElement: DataElement = {
  uri: "https://schema.undata.live/elements/age_x7k2m9",
  semantic: { ontology_term: null, data_type: "float", unit: "year", constraints: null },
  provenance: [{ source: "bids", class: "Participant", name: "subject_age", description: "Age", required: true, multivalued: null }],
};

describe("ComparisonView", () => {
  afterEach(() => cleanup());

  it("renders two columns with element names", () => {
    const elB: DataElement = {
      uri: "https://schema.undata.live/elements/age_y8l3n0",
      semantic: { ...baseElement.semantic },
      provenance: [{ source: "nwb", class: "Subject", name: "participant_age", description: null, required: null, multivalued: null }],
    };
    render(<ComparisonView elementA={baseElement} elementB={elB} />);
    expect(screen.getAllByText("subject_age").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("participant_age").length).toBeGreaterThanOrEqual(1);
  });

  it("marks identical field values as matching", () => {
    const elB: DataElement = { ...baseElement, uri: "https://schema.undata.live/elements/age_other" };
    render(<ComparisonView elementA={baseElement} elementB={elB} />);
    const matchIcons = screen.getAllByLabelText("matching");
    expect(matchIcons.length).toBeGreaterThan(0);
  });

  it("marks differing field values as differs", () => {
    const elB: DataElement = {
      uri: "https://schema.undata.live/elements/age_str",
      semantic: { ontology_term: null, data_type: "string", unit: null, constraints: null },
      provenance: [{ source: "nwb", class: "Subject", name: "age", description: null, required: null, multivalued: null }],
    };
    render(<ComparisonView elementA={baseElement} elementB={elB} />);
    const diffIcons = screen.getAllByLabelText("differs");
    expect(diffIcons.length).toBeGreaterThan(0);
  });
});

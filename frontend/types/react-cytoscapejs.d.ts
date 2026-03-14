declare module "react-cytoscapejs" {
  import type { Component } from "react";
  import type cytoscape from "cytoscape";

  interface CytoscapeComponentProps {
    elements: cytoscape.ElementDefinition[];
    layout?: cytoscape.LayoutOptions;
    style?: React.CSSProperties;
    stylesheet?: cytoscape.Stylesheet[];
    cy?: (cy: cytoscape.Core) => void;
    className?: string;
  }

  const CytoscapeComponent: React.ComponentType<CytoscapeComponentProps>;
  export default CytoscapeComponent;
}

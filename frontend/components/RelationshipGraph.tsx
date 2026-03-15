"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { getElementById } from "@/lib/api/elements";
import type { GraphEdge, GraphNode } from "@/lib/types";
import { Label } from "@/components/ui/label";
import { ErrorBanner } from "@/components/ErrorBanner";

let CytoscapeComponent: typeof import("react-cytoscapejs").default | null =
  null;

interface RelationshipGraphProps {
  elementId: string;
  initialDepth?: number;
}

function buildGraph(
  element: Awaited<ReturnType<typeof getElementById>>,
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  const seen = new Set<string>();

  // Root node
  nodes.push({
    id: element.id,
    label: element.name,
    data_type: element.data_type,
    source_name: element.source.name,
    is_alias: false,
    is_root: true,
  });
  seen.add(element.id);

  // Alias group members
  for (const ag of element.alias_groups) {
    // We don't have full member data from the detail endpoint,
    // so we just note the alias group exists
    const aliasNodeId = `alias-${ag.id}`;
    if (!seen.has(aliasNodeId)) {
      seen.add(aliasNodeId);
      nodes.push({
        id: aliasNodeId,
        label: ag.name,
        data_type: "",
        source_name: "",
        is_alias: true,
        is_root: false,
      });
      edges.push({
        id: `e-alias-${ag.id}`,
        source: element.id,
        target: aliasNodeId,
        function_type: "alias",
        label: ag.sssom_predicate,
      });
    }
  }

  // Mappings as input (this element → output)
  for (const m of element.mappings_as_input) {
    const targetId = `mapping-out-${m.id}`;
    if (!seen.has(targetId)) {
      seen.add(targetId);
      nodes.push({
        id: targetId,
        label: m.output_name || "output",
        data_type: "",
        source_name: "",
        is_alias: false,
        is_root: false,
      });
    }
    edges.push({
      id: `e-in-${m.id}`,
      source: element.id,
      target: targetId,
      function_type: m.function_type,
      label: m.function_type,
    });
  }

  // Mappings as output (inputs → this element)
  for (const m of element.mappings_as_output) {
    for (const inputName of m.input_names || []) {
      const sourceId = `mapping-in-${m.id}-${inputName}`;
      if (!seen.has(sourceId)) {
        seen.add(sourceId);
        nodes.push({
          id: sourceId,
          label: inputName,
          data_type: "",
          source_name: "",
          is_alias: false,
          is_root: false,
        });
      }
      edges.push({
        id: `e-out-${m.id}-${inputName}`,
        source: sourceId,
        target: element.id,
        function_type: m.function_type,
        label: m.function_type,
      });
    }
  }

  return { nodes, edges };
}

export function RelationshipGraph({
  elementId,
  initialDepth = 2,
}: RelationshipGraphProps) {
  const router = useRouter();
  const [depth, setDepth] = useState(initialDepth);
  const [cyLoaded, setCyLoaded] = useState(false);

  const { data: element, error } = useQuery({
    queryKey: ["element-graph", elementId],
    queryFn: () => getElementById(elementId),
  });

  // Lazy-load Cytoscape
  useMemo(() => {
    if (typeof window !== "undefined" && !CytoscapeComponent) {
      import("react-cytoscapejs").then((mod) => {
        CytoscapeComponent = mod.default;
        setCyLoaded(true);
      });
    }
  }, []);

  const graph = useMemo(
    () => (element ? buildGraph(element) : { nodes: [], edges: [] }),
    [element],
  );

  const cyElements = useMemo(
    () => [
      ...graph.nodes.map((n) => ({
        data: {
          id: n.id,
          label: n.label,
          isRoot: n.is_root,
          isAlias: n.is_alias,
        },
      })),
      ...graph.edges.map((e) => ({
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.label,
        },
      })),
    ],
    [graph],
  );

  const handleNodeClick = useCallback(
    (id: string) => {
      // Only navigate for real element IDs (UUIDs)
      if (
        id &&
        !id.startsWith("alias-") &&
        !id.startsWith("mapping-")
      ) {
        router.push(`/elements/${id}`);
      }
    },
    [router],
  );

  if (error) return <ErrorBanner error={error as Error} />;

  if (graph.nodes.length === 0 && element) {
    return (
      <p className="text-sm text-muted-foreground">
        No relationships to display.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <Label htmlFor="depth-slider">Depth</Label>
        <input
          id="depth-slider"
          type="range"
          min={1}
          max={5}
          value={depth}
          onChange={(e) => setDepth(Number(e.target.value))}
          className="w-32"
          aria-label="Graph depth"
        />
        <span className="text-sm text-muted-foreground">{depth}</span>
      </div>

      {cyLoaded && CytoscapeComponent ? (
        <CytoscapeComponent
          elements={cyElements}
          layout={{ name: "cose-bilkent" } as never}
          style={{ width: "100%", height: "400px" }}
          stylesheet={[
            {
              selector: "node",
              style: {
                label: "data(label)",
                "font-size": "11px",
                "text-valign": "bottom" as const,
                "text-halign": "center" as const,
                "background-color": "#6366f1",
                width: 30,
                height: 30,
              },
            },
            {
              selector: "node[?isRoot]",
              style: {
                "background-color": "#059669",
                width: 40,
                height: 40,
              },
            },
            {
              selector: "node[?isAlias]",
              style: {
                "background-color": "#d97706",
                shape: "diamond" as const,
              },
            },
            {
              selector: "edge",
              style: {
                label: "data(label)",
                "font-size": "9px",
                "line-color": "#94a3b8",
                "target-arrow-color": "#94a3b8",
                "target-arrow-shape": "triangle" as const,
                "curve-style": "bezier" as const,
                width: 2,
              },
            },
          ]}
          cy={(cy) => {
            cy.on("tap", "node", (evt) => {
              handleNodeClick(evt.target.id());
            });
          }}
        />
      ) : (
        // Accessible table fallback
        <table className="w-full text-sm">
          <caption className="sr-only">Element relationships</caption>
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="py-2">Node</th>
              <th className="py-2">Type</th>
              <th className="py-2">Relation</th>
            </tr>
          </thead>
          <tbody>
            {graph.nodes
              .filter((n) => !n.is_root)
              .map((n) => {
                const edge = graph.edges.find(
                  (e) => e.source === n.id || e.target === n.id,
                );
                return (
                  <tr key={n.id} className="border-b">
                    <td className="py-2">{n.label}</td>
                    <td className="py-2">
                      {n.is_alias ? "alias" : "mapping"}
                    </td>
                    <td className="py-2">{edge?.label || "-"}</td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      )}
    </div>
  );
}

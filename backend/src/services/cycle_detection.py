"""CycleDetector — pure Python iterative DFS cycle detection for mapping DAG.

Importable without app context; no database or FastAPI dependencies.
"""

from __future__ import annotations


class CycleDetector:
    @staticmethod
    def detect_cycle_dfs(
        adjacency: list[tuple[str, str]],
        proposed_input_ids: list[str],
        proposed_output_id: str,
    ) -> list[str] | None:
        """Detect a cycle in the proposed augmented mapping graph.

        The mapping graph is directed: inputs → output.
        ``adjacency`` is the current list of (from_id, to_id) edges.
        The proposed edges are: each id in ``proposed_input_ids`` → ``proposed_output_id``.

        Returns the first cycle path found (list of node IDs), or None if the
        proposed addition does not create a cycle.

        The check is: after adding the proposed edges, is there a path from
        ``proposed_output_id`` back to any of the ``proposed_input_ids``?
        That would mean the output is reachable from an input but also the
        input is reachable from the output — a cycle.

        We use iterative DFS to avoid Python recursion limits.
        """
        # Build adjacency list (from → list of tos)
        adj: dict[str, list[str]] = {}
        for frm, to in adjacency:
            adj.setdefault(frm, []).append(to)

        # Add proposed edges
        for inp_id in proposed_input_ids:
            adj.setdefault(inp_id, []).append(proposed_output_id)

        # DFS from proposed_output_id to see if we can reach any proposed_input_id
        # (which would form a cycle, because proposed_input → proposed_output → ... → proposed_input)
        # Also check self-loop: if proposed_output_id is in proposed_input_ids
        if proposed_output_id in proposed_input_ids:
            return [proposed_output_id, proposed_output_id]

        targets = set(proposed_input_ids)

        # Iterative DFS with path tracking
        stack: list[tuple[str, list[str]]] = [(proposed_output_id, [proposed_output_id])]
        visited: set[str] = set()

        while stack:
            node, path = stack.pop()
            if node in visited:
                continue
            visited.add(node)

            for neighbor in adj.get(node, []):
                if neighbor in targets:
                    return path + [neighbor]
                if neighbor not in visited:
                    stack.append((neighbor, path + [neighbor]))

        return None

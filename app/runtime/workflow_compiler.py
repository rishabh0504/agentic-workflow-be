from typing import Dict, Any, List, Tuple
from app.runtime.contracts.compatibility import ContractCompatibility


class WorkflowCompiler:
    """
    Validates and normalizes visual canvas ReactFlow graphs into executable DAGs.
    Enforces structural, node-level, and edge contract compatibility before saving or publishing.
    """

    @staticmethod
    def validate_graph(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        if not nodes:
            return False, ["Workflow graph contains no nodes."]

        # 1. Structural Checks
        start_nodes = [n for n in nodes if n.get("type") in ("start", "startNode")]
        end_nodes = [n for n in nodes if n.get("type") in ("end", "endNode")]

        if len(start_nodes) != 1:
            errors.append(f"Workflow must have exactly 1 Start node. Found {len(start_nodes)}.")

        if len(end_nodes) < 1:
            errors.append("Workflow must have at least 1 End terminal node.")

        node_map = {n.get("id"): n for n in nodes if n.get("id")}
        node_ids = set(node_map.keys())

        # 2. Edge Integrity & Contract Compatibility Checking
        for edge in edges:
            src = edge.get("source")
            tgt = edge.get("target")
            if src not in node_ids:
                errors.append(f"Edge references non-existent source node '{src}'.")
                continue
            if tgt not in node_ids:
                errors.append(f"Edge references non-existent target node '{tgt}'.")
                continue

            producer_node = node_map[src]
            consumer_node = node_map[tgt]

            # If consumer node has explicit inputMapping (Mode B: MAPPED), validate JSONPath format
            consumer_data = consumer_node.get("data") or {}
            input_mapping = consumer_data.get("inputMapping")

            if input_mapping and isinstance(input_mapping, dict) and len(input_mapping) > 0:
                for target_field, jsonpath_expr in input_mapping.items():
                    if not isinstance(jsonpath_expr, str) or not jsonpath_expr.startswith("$"):
                        errors.append(f"Invalid JSONPath mapping in node '{tgt}' for field '{target_field}': '{jsonpath_expr}'. Must start with '$'.")
            else:
                # Mode A: DIRECT - Check schema compatibility if both declare schemas
                prod_data = producer_node.get("data") or {}
                prod_out = prod_data.get("outputSchema")
                cons_in = consumer_data.get("inputSchema")

                if prod_out and cons_in:
                    compat = ContractCompatibility.check(prod_out, cons_in)
                    if not compat.is_compatible:
                        errors.append(
                            f"Contract mismatch on edge '{src}' -> '{tgt}': {compat.reason}"
                        )

        # 3. Node Configuration Checks
        for n in nodes:
            ntype = n.get("type")
            data = n.get("data") or {}
            nid = n.get("id")

            if ntype in ("agent", "agentNode") and not data.get("agentId") and not data.get("id") and not data.get("name"):
                errors.append(f"Agent node '{nid}' is missing an assigned Agent.")

            if ntype in ("guardrail", "guardrailNode") and not data.get("guardrailId") and not data.get("id"):
                errors.append(f"Guardrail node '{nid}' is missing an assigned Guardrail Policy.")

        return len(errors) == 0, errors

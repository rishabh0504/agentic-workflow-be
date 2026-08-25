import re
from typing import Any, Dict, Optional


class JSONPathEvaluator:
    """
    Safely resolves path references against Workflow Execution State.
    Supported expressions:
      - $workflow.input.message
      - $nodes.<node_id>.output.market_summary
      - $nodes.<node_id>.output.verified_facts[0]
    """

    @classmethod
    def evaluate(cls, path_expr: str, state: Dict[str, Any]) -> Any:
        if not isinstance(path_expr, str):
            return path_expr

        trimmed = path_expr.strip()
        if not trimmed.startswith("$"):
            return path_expr

        # Normalize prefix
        # Handle $workflow.input.<field>
        if trimmed.startswith("$workflow.input"):
            sub_path = trimmed[len("$workflow.input"):].lstrip(".")
            input_root = state.get("node_outputs", {}).get("input", {}) or state.get("input", {})
            return cls._traverse(input_root, sub_path)

        # Handle $nodes.<node_id>.output.<field>
        node_match = re.match(r"^\$nodes\.([a-zA-Z0-9_\-]+)\.output(?:\.(.*))?$", trimmed)
        if node_match:
            node_id = node_match.group(1)
            sub_path = node_match.group(2) or ""
            node_output = state.get("node_outputs", {}).get(node_id, {})
            if not sub_path:
                return node_output
            return cls._traverse(node_output, sub_path)

        # Direct $node_outputs.<node_id>
        if trimmed.startswith("$"):
            raw_path = trimmed[1:].lstrip(".")
            return cls._traverse(state.get("node_outputs", {}), raw_path)

        return None

    @classmethod
    def _traverse(cls, obj: Any, path: str) -> Any:
        if not path:
            return obj
        tokens = path.split(".")
        current = obj

        for token in tokens:
            if current is None:
                return None

            # Handle array index e.g. items[0]
            array_match = re.match(r"^([a-zA-Z0-9_-]+)\[(\d+)\]$", token)
            if array_match:
                key, idx = array_match.group(1), int(array_match.group(2))
                if isinstance(current, dict) and key in current:
                    current = current[key]
                    if isinstance(current, list) and 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return None
                else:
                    return None
            else:
                if isinstance(current, dict):
                    current = current.get(token)
                else:
                    return None

        return current

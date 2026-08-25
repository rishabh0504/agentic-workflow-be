from typing import Dict, Any
from app.runtime.contracts.json_path import JSONPathEvaluator


class ContractMapper:
    """Executes explicit multi-source field mappings into the structured shape expected by a consumer."""

    @staticmethod
    def map_inputs(mapping_config: Dict[str, str], workflow_state: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for target_key, source_expr in mapping_config.items():
            result[target_key] = JSONPathEvaluator.evaluate(source_expr, workflow_state)
        return result

from typing import Dict, Any, Optional, List
from app.runtime.contracts.models import ResolvedInputPayload, ContractValidationResult
from app.runtime.contracts.validator import ContractValidator
from app.runtime.contracts.mapping import ContractMapper
from app.runtime.contracts.errors import ContractValidationError


class ContractResolver:
    """
    Core Runtime Engine that resolves, transforms, and validates inputs between workflow nodes.
    Supports Mode A (DIRECT) and Mode B (MAPPED).
    """

    @classmethod
    def resolve_and_validate_input(
        cls,
        consumer_node: Dict[str, Any],
        workflow_state: Dict[str, Any],
        incoming_edges: List[Dict[str, Any]],
        consumer_schema: Optional[Dict[str, Any]] = None,
    ) -> ResolvedInputPayload:
        node_data = consumer_node.get("data", {})
        input_mapping = node_data.get("inputMapping")

        # 1. Mode B: MAPPED Input Resolution
        if input_mapping and isinstance(input_mapping, dict) and len(input_mapping) > 0:
            mapped_payload = ContractMapper.map_inputs(input_mapping, workflow_state)
            
            # Validate mapped payload against consumer input schema
            if consumer_schema:
                val_res = ContractValidator.validate(mapped_payload, consumer_schema, contract_name=consumer_node.get("id", "node"))
                if not val_res.is_valid:
                    error_msg = "; ".join([f"{e.path}: {e.message}" for e in val_res.errors])
                    raise ContractValidationError(f"Mapped input validation failed for node '{consumer_node.get('id')}': {error_msg}", val_res)

            return ResolvedInputPayload(
                payload=mapped_payload,
                mode="MAPPED",
                source_nodes=[e.get("source") for e in incoming_edges if "source" in e],
            )

        # 2. Mode A: DIRECT Input Resolution
        resolved_payload: Dict[str, Any] = {}

        if len(incoming_edges) == 1:
            pred_id = incoming_edges[0].get("source")
            pred_output = workflow_state.get("node_outputs", {}).get(pred_id, {})
            if isinstance(pred_output, dict):
                resolved_payload = pred_output
            else:
                resolved_payload = {"value": pred_output}
        elif len(incoming_edges) == 0:
            # Kickoff from global workflow input
            resolved_payload = workflow_state.get("node_outputs", {}).get("input", {}) or workflow_state.get("input", {})
        else:
            # Multi-edge merge
            for edge in incoming_edges:
                p_id = edge.get("source")
                p_out = workflow_state.get("node_outputs", {}).get(p_id, {})
                if isinstance(p_out, dict):
                    resolved_payload.update(p_out)

        # Validate Direct payload against consumer schema
        if consumer_schema:
            val_res = ContractValidator.validate(resolved_payload, consumer_schema, contract_name=consumer_node.get("id", "node"))
            if not val_res.is_valid:
                error_msg = "; ".join([f"{e.path}: {e.message}" for e in val_res.errors])
                raise ContractValidationError(f"Direct input validation failed for node '{consumer_node.get('id')}': {error_msg}", val_res)

        return ResolvedInputPayload(
            payload=resolved_payload,
            mode="DIRECT",
            source_nodes=[e.get("source") for e in incoming_edges if "source" in e],
        )

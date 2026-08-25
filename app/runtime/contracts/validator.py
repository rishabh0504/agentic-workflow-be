from typing import Dict, Any, List
import jsonschema
from jsonschema import Draft7Validator
from app.runtime.contracts.models import ContractValidationResult, SchemaPropertyValidationError


class ContractValidator:
    """Validates structured payloads against standard JSON Schema specifications."""

    @staticmethod
    def validate(payload: Any, schema: Dict[str, Any], contract_name: str = "custom") -> ContractValidationResult:
        if not schema or not isinstance(schema, dict):
            # If schema is empty, allow pass-through
            return ContractValidationResult(is_valid=True, contract_name=contract_name)

        validator = Draft7Validator(schema)
        errors: List[SchemaPropertyValidationError] = []

        for err in validator.iter_errors(payload):
            field_path = "$." + ".".join([str(p) for p in err.path]) if err.path else "$ (root)"
            expected_type = err.validator_value if err.validator == "type" else str(err.validator)
            actual_val = err.instance
            actual_type = type(actual_val).__name__

            errors.append(
                SchemaPropertyValidationError(
                    path=field_path,
                    expected=str(expected_type),
                    actual=actual_type,
                    message=err.message,
                )
            )

        return ContractValidationResult(
            is_valid=len(errors) == 0,
            contract_name=contract_name,
            errors=errors,
        )

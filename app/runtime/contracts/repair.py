import json
from typing import Dict, Any, List, Optional
from app.runtime.contracts.models import ContractValidationResult


class SchemaRepairLoop:
    """Constructs explicit self-correction prompts when an LLM returns malformed or invalid output."""

    @staticmethod
    def build_repair_prompt(
        original_prompt: str,
        invalid_raw_output: Any,
        expected_schema: Dict[str, Any],
        validation_result: ContractValidationResult,
        attempt: int = 1,
    ) -> str:
        error_lines = [f"- Path '{err.path}': {err.message} (Expected {err.expected}, got {err.actual})" for err in validation_result.errors]
        error_summary = "\n".join(error_lines)

        raw_preview = json.dumps(invalid_raw_output, indent=2) if isinstance(invalid_raw_output, (dict, list)) else str(invalid_raw_output)

        return (
            f"Your previous output violated the required JSON Schema contract (Attempt {attempt} of 2).\n\n"
            f"### Validation Errors:\n{error_summary}\n\n"
            f"### Target Required JSON Schema:\n```json\n{json.dumps(expected_schema, indent=2)}\n```\n\n"
            f"### Your Previous Output:\n```\n{raw_preview}\n```\n\n"
            f"### Task:\n"
            f"Correct the errors above and return ONLY a valid JSON object matching the target schema exactly without extra commentary or markdown fencing."
        )

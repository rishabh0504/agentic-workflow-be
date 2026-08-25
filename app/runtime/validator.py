from typing import Any, Dict, Tuple, Optional
import jsonschema
from jsonschema.exceptions import ValidationError, SchemaError


def validate_json_schema(data: Any, schema: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
    """
    Validates data against a JSON Schema Draft-07 dictionary.
    Returns (is_valid, error_message).
    """
    if not schema or not isinstance(schema, dict) or not schema.get("properties") and not schema.get("type"):
        return True, None

    try:
        jsonschema.validate(instance=data, schema=schema)
        return True, None
    except ValidationError as e:
        field_path = " -> ".join([str(p) for p in e.path]) if e.path else "root"
        return False, f"Validation error at '{field_path}': {e.message}"
    except SchemaError as e:
        return False, f"Invalid JSON Schema definition: {e.message}"
    except Exception as e:
        return False, f"Schema validation error: {str(e)}"

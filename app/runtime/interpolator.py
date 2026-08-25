import re
from typing import Any, Dict


TEMPLATE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_\.]+)\s*\}\}")


def get_nested_value(data: Any, path: str) -> Any:
    """Safely extracts a nested property via dot-notation path (e.g. 'input.customer.id')"""
    parts = path.split(".")
    current = data

    for part in parts:
        if isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                return None
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return None

    return current


def interpolate_string(template: str, context: Dict[str, Any]) -> Any:
    """
    Interpolates a string template with variables from context.
    If the template is exactly '{{path}}', returns the typed value (e.g. int/bool/dict).
    Otherwise returns string with replaced tokens.
    """
    if not isinstance(template, str):
        return template

    stripped = template.strip()
    # Direct single-token replacement returning raw type
    single_match = re.fullmatch(r"\{\{\s*([a-zA-Z0-9_\.]+)\s*\}\}", stripped)
    if single_match:
        val = get_nested_value(context, single_match.group(1))
        return val if val is not None else ""

    def replacer(match):
        path = match.group(1)
        val = get_nested_value(context, path)
        return str(val) if val is not None else ""

    return TEMPLATE_PATTERN.sub(replacer, template)


def interpolate_data(data: Any, context: Dict[str, Any]) -> Any:
    """Recursively interpolates strings inside dictionaries, lists, and primitives."""
    if isinstance(data, str):
        return interpolate_string(data, context)
    elif isinstance(data, dict):
        return {k: interpolate_data(v, context) for k, v in data.items()}
    elif isinstance(data, list):
        return [interpolate_data(elem, context) for elem in data]
    return data

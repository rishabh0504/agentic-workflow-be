from typing import Dict, Any, List, Optional
from app.runtime.contracts.models import CompatibilityResult


class ContractCompatibility:
    """
    Recursively validates if a Producer Output Contract satisfies Consumer Input Contract.
    Rule: Consumer Requirements ⊆ Producer Guarantees.
    """

    SUPPORTED_TYPES = {"object", "string", "number", "integer", "boolean", "array", "null"}

    @classmethod
    def check(cls, producer_schema: Optional[Dict[str, Any]], consumer_schema: Optional[Dict[str, Any]]) -> CompatibilityResult:
        # If either schema is empty/not specified, allow loose coupling
        if not producer_schema or not consumer_schema:
            return CompatibilityResult(is_compatible=True)

        missing_fields: List[str] = []
        type_mismatches: List[Dict[str, str]] = []

        cls._check_recursive(producer_schema, consumer_schema, "$", missing_fields, type_mismatches)

        if missing_fields or type_mismatches:
            reasons = []
            if missing_fields:
                reasons.append(f"Missing required fields: {', '.join(missing_fields)}")
            if type_mismatches:
                for tm in type_mismatches:
                    reasons.append(f"Type mismatch at '{tm['path']}': Producer provides '{tm['producer_type']}' but Consumer requires '{tm['consumer_type']}'")
            return CompatibilityResult(
                is_compatible=False,
                reason="; ".join(reasons),
                missing_fields=missing_fields,
                type_mismatches=type_mismatches,
            )

        return CompatibilityResult(is_compatible=True)

    @classmethod
    def _check_recursive(
        cls,
        prod: Dict[str, Any],
        cons: Dict[str, Any],
        path: str,
        missing: List[str],
        mismatches: List[Dict[str, str]],
    ):
        prod_type = prod.get("type", "object")
        cons_type = cons.get("type", "object")

        # 1. Check Root/Property Type Matching
        if prod_type != cons_type:
            # integer is compatible with number
            if not (prod_type == "integer" and cons_type == "number"):
                mismatches.append({
                    "path": path,
                    "producer_type": prod_type,
                    "consumer_type": cons_type,
                })
                return

        # 2. Object Recursive Check
        if cons_type == "object":
            cons_req = cons.get("required", [])
            cons_props = cons.get("properties", {})
            prod_props = prod.get("properties", {})

            # Every required field in consumer MUST exist in producer properties
            for req_field in cons_req:
                if req_field not in prod_props:
                    missing.append(f"{path}.{req_field}" if path != "$" else req_field)

            # For every shared property, recurse into its definition
            for key, cons_child in cons_props.items():
                if key in prod_props:
                    prod_child = prod_props[key]
                    cls._check_recursive(prod_child, cons_child, f"{path}.{key}", missing, mismatches)

        # 3. Array Items Recursive Check
        elif cons_type == "array":
            cons_items = cons.get("items")
            prod_items = prod.get("items")

            if cons_items and prod_items:
                if isinstance(cons_items, dict) and isinstance(prod_items, dict):
                    cls._check_recursive(prod_items, cons_items, f"{path}[]", missing, mismatches)
                elif isinstance(cons_items, str) and isinstance(prod_items, str):
                    if prod_items != cons_items:
                        mismatches.append({
                            "path": f"{path}[]",
                            "producer_type": prod_items,
                            "consumer_type": cons_items,
                        })

        # 4. Enum Check
        if "enum" in cons:
            cons_enum = set(cons["enum"])
            prod_enum = set(prod.get("enum", []))
            if prod_enum and not cons_enum.issuperset(prod_enum):
                mismatches.append({
                    "path": path,
                    "producer_type": f"enum{list(prod_enum)}",
                    "consumer_type": f"enum{list(cons_enum)}",
                })

"""Utilities for preparing Pydantic JSON schemas for the Claude API.

The Claude json_schema structured output format requires:
1. No $ref/$defs — all definitions must be inlined
2. additionalProperties: false on all object types
"""

from __future__ import annotations

import copy


def prepare_schema_for_claude(schema: dict) -> dict:
    """Inline $ref definitions and add additionalProperties: false to all objects.

    Takes a Pydantic model_json_schema() output and returns a schema
    compatible with Claude's json_schema output format.
    """
    schema = copy.deepcopy(schema)
    defs = schema.pop("$defs", {})

    def _resolve(node: dict | list) -> dict | list:
        if isinstance(node, list):
            return [_resolve(item) for item in node]
        if not isinstance(node, dict):
            return node

        # Resolve $ref
        if "$ref" in node:
            ref_path = node["$ref"]  # e.g. "#/$defs/DiscoveredEntity"
            ref_name = ref_path.rsplit("/", 1)[-1]
            resolved = copy.deepcopy(defs[ref_name])
            # Merge any sibling keys (rare but possible)
            for k, v in node.items():
                if k != "$ref":
                    resolved[k] = v
            return _resolve(resolved)

        # Recurse into all dict values
        result = {}
        for key, value in node.items():
            if isinstance(value, dict):
                result[key] = _resolve(value)
            elif isinstance(value, list):
                result[key] = [_resolve(item) if isinstance(item, (dict, list)) else item for item in value]
            else:
                result[key] = value

        # Ensure additionalProperties: false on all object types
        if result.get("type") == "object" and "additionalProperties" not in result:
            result["additionalProperties"] = False

        return result

    return _resolve(schema)

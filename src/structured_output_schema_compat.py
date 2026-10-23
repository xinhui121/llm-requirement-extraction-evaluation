#!/usr/bin/env python3
"""Local preflight for the OpenAI strict Structured Outputs schema subset.

This deliberately checks the provider restrictions relevant to this experiment
before a request is sent. It is not a replacement for server-side validation.
"""

from __future__ import annotations


# OpenAI's strict Structured Outputs guide documents `anyOf`, not the other
# JSON-Schema composition keywords. `uniqueItems` is additionally rejected by
# the API response captured for this experiment.
UNSUPPORTED_KEYWORDS = {
    "allOf",
    "not",
    "dependentRequired",
    "dependentSchemas",
    "if",
    "then",
    "else",
    "oneOf",
    "uniqueItems",
    "contains",
    "minContains",
    "maxContains",
    "unevaluatedItems",
    "unevaluatedProperties",
    "propertyNames",
    "patternProperties",
    "default",
}


def _is_object_schema(schema: dict) -> bool:
    schema_type = schema.get("type")
    return schema_type == "object" or (isinstance(schema_type, list) and "object" in schema_type)


def find_openai_strict_compatibility_issues(schema: dict) -> list[str]:
    """Return actionable path-qualified issues without modifying the schema."""
    issues: list[str] = []

    def visit(node, path: str) -> None:
        if isinstance(node, dict):
            for key in sorted(UNSUPPORTED_KEYWORDS & set(node)):
                issues.append(f"{path}: {key!r} is not permitted by OpenAI strict Structured Outputs")
            if _is_object_schema(node):
                if node.get("additionalProperties") is not False:
                    issues.append(f"{path}: object schemas must set additionalProperties=false")
                properties = node.get("properties", {})
                required = set(node.get("required", []))
                if isinstance(properties, dict):
                    missing_required = sorted(set(properties) - required)
                    if missing_required:
                        issues.append(f"{path}: every declared property must be required; missing {missing_required}")
            for key, value in node.items():
                visit(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                visit(value, f"{path}[{index}]")

    if not isinstance(schema, dict):
        return ["$: schema must be a JSON object"]
    if not _is_object_schema(schema):
        issues.append("$: root schema must be an object")
    visit(schema, "$")
    return issues


def assert_openai_strict_schema_compatible(schema: dict) -> None:
    issues = find_openai_strict_compatibility_issues(schema)
    if issues:
        raise ValueError("OpenAI strict Structured Outputs schema incompatibility: " + "; ".join(issues))

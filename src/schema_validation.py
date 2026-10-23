#!/usr/bin/env python3
"""Small dependency-free validator for the JSON-Schema subset used here."""

from __future__ import annotations

import json
import re
from pathlib import Path


class SchemaValidationError(ValueError):
    pass


def load_schema(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_ref(root, ref):
    if not ref.startswith("#/"):
        raise SchemaValidationError(f"Unsupported external $ref: {ref}")
    value = root
    for token in ref[2:].split("/"):
        value = value[token.replace("~1", "/").replace("~0", "~")]
    return value


def _type_ok(value, expected):
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return False


def validate(instance, schema, *, root=None, path="$"):
    root = root or schema
    if "$ref" in schema:
        return validate(instance, _resolve_ref(root, schema["$ref"]), root=root, path=path)
    if "oneOf" in schema:
        successes = 0
        for option in schema["oneOf"]:
            try:
                validate(instance, option, root=root, path=path)
                successes += 1
            except SchemaValidationError:
                pass
        if successes != 1:
            raise SchemaValidationError(f"{path}: expected exactly one oneOf match, got {successes}")
        return
    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaValidationError(f"{path}: {instance!r} is not in {schema['enum']!r}")
    expected = schema.get("type")
    if expected:
        choices = expected if isinstance(expected, list) else [expected]
        if not any(_type_ok(instance, item) for item in choices):
            raise SchemaValidationError(f"{path}: expected type {choices}, got {type(instance).__name__}")
    if isinstance(instance, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in instance]
        if missing:
            raise SchemaValidationError(f"{path}: missing required keys {missing}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = sorted(set(instance) - set(properties))
            if extra:
                raise SchemaValidationError(f"{path}: unexpected keys {extra}")
        for key, value in instance.items():
            if key in properties:
                validate(value, properties[key], root=root, path=f"{path}.{key}")
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            raise SchemaValidationError(f"{path}: too few items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise SchemaValidationError(f"{path}: too many items")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True, ensure_ascii=False) for item in instance]
            if len(encoded) != len(set(encoded)):
                raise SchemaValidationError(f"{path}: duplicate array items")
        for index, item in enumerate(instance):
            validate(item, schema.get("items", {}), root=root, path=f"{path}[{index}]")
    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            raise SchemaValidationError(f"{path}: string is too short")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            raise SchemaValidationError(f"{path}: string is too long")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            raise SchemaValidationError(f"{path}: string does not match {schema['pattern']}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise SchemaValidationError(f"{path}: number is below minimum")


def validate_from_file(instance, schema_path: Path):
    schema = load_schema(schema_path)
    validate(instance, schema, root=schema)

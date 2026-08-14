"""Small Draft 2020-12 subset used to test the repository's offline schemas.

The benchmark tooling intentionally has no third-party Python dependency.  This
validator implements only the keywords used by the repository's published
benchmark schemas so positive and negative contract examples exercise those
schemas, not a second hand-written description of them.
"""

from __future__ import annotations

import re
from typing import Any


class ValidationError(AssertionError):
    pass


def _resolve(root: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise ValidationError(f"unsupported schema reference: {reference}")
    value: Any = root
    for encoded in reference[2:].split("/"):
        token = encoded.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, dict) or token not in value:
            raise ValidationError(f"unresolved schema reference: {reference}")
        value = value[token]
    if not isinstance(value, dict):
        raise ValidationError(f"schema reference is not an object: {reference}")
    return value


def _matches_type(value: object, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    raise ValidationError(f"unsupported schema type: {expected}")


def validate(instance: object, schema: dict[str, Any]) -> None:
    _validate(instance, schema, schema, "$")


def _validate(
    instance: object, schema: dict[str, Any], root: dict[str, Any], path: str
) -> None:
    if "$ref" in schema:
        _validate(instance, _resolve(root, str(schema["$ref"])), root, path)

    for child in schema.get("allOf", []):
        _validate(instance, child, root, path)

    if "if" in schema:
        try:
            _validate(instance, schema["if"], root, path)
        except ValidationError:
            branch = schema.get("else")
        else:
            branch = schema.get("then")
        if branch is not None:
            _validate(instance, branch, root, path)

    if "oneOf" in schema:
        matches = 0
        for child in schema["oneOf"]:
            try:
                _validate(instance, child, root, path)
            except ValidationError:
                continue
            matches += 1
        if matches != 1:
            raise ValidationError(f"{path} must match exactly one schema branch")

    if "const" in schema and instance != schema["const"]:
        raise ValidationError(f"{path} does not match const")
    if "enum" in schema and instance not in schema["enum"]:
        raise ValidationError(f"{path} is outside enum")

    expected_type = schema.get("type")
    if expected_type is not None:
        expected = [expected_type] if isinstance(expected_type, str) else expected_type
        if not any(_matches_type(instance, item) for item in expected):
            raise ValidationError(f"{path} has the wrong type")

    if isinstance(instance, dict):
        required = set(schema.get("required", []))
        missing = required - instance.keys()
        if missing:
            raise ValidationError(f"{path} is missing {sorted(missing)}")
        properties = schema.get("properties", {})
        for name, child in properties.items():
            if name in instance:
                _validate(instance[name], child, root, f"{path}.{name}")
        for trigger, dependencies in schema.get("dependentRequired", {}).items():
            if trigger in instance:
                missing_dependencies = set(dependencies) - instance.keys()
                if missing_dependencies:
                    raise ValidationError(
                        f"{path}.{trigger} is missing dependencies {sorted(missing_dependencies)}"
                    )
        if schema.get("additionalProperties") is False:
            unexpected = instance.keys() - properties.keys()
            if unexpected:
                raise ValidationError(f"{path} has unknown fields {sorted(unexpected)}")
        minimum_properties = schema.get("minProperties")
        if minimum_properties is not None and len(instance) < minimum_properties:
            raise ValidationError(f"{path} has too few properties")

    if isinstance(instance, list):
        minimum_items = schema.get("minItems")
        if minimum_items is not None and len(instance) < minimum_items:
            raise ValidationError(f"{path} has too few items")
        if "items" in schema:
            for index, item in enumerate(instance):
                _validate(item, schema["items"], root, f"{path}[{index}]")

    if isinstance(instance, str):
        minimum_length = schema.get("minLength")
        if minimum_length is not None and len(instance) < minimum_length:
            raise ValidationError(f"{path} is too short")
        pattern = schema.get("pattern")
        if pattern is not None and re.search(pattern, instance) is None:
            raise ValidationError(f"{path} does not match its pattern")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        if minimum is not None and instance < minimum:
            raise ValidationError(f"{path} is below its minimum")

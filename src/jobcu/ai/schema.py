"""Turns Jobcu's answer formats (Pydantic models) into JSON schemas every provider accepts,
and reads JSON back out of a model's reply.

Providers accept different parts of JSON Schema. The common safe subset is: no
references, every object closed (`additionalProperties: false`), every property
required (optional values are nullable instead), and no numeric or length limits.
Pydantic still checks those limits after the answer arrives.
"""

import json
import re
from typing import Any

from pydantic import BaseModel

_DROP_KEYS = {
    "title",
    "default",
    "examples",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minItems",
    "maxItems",
    "uniqueItems",
}


def strict_json_schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})
    return _clean(schema, defs)


def _clean(node: Any, defs: dict) -> Any:
    if isinstance(node, list):
        return [_clean(item, defs) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        target = defs[node["$ref"].rsplit("/", 1)[-1]]
        merged = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
        return _clean(merged, defs)
    cleaned = {k: _clean(v, defs) for k, v in node.items() if k not in _DROP_KEYS}
    if cleaned.get("type") == "object" or "properties" in cleaned:
        cleaned["type"] = "object"
        cleaned.setdefault("properties", {})
        cleaned["required"] = list(cleaned["properties"])
        cleaned["additionalProperties"] = False
    # A single-option allOf (Pydantic uses it for described references) is unwrapped.
    if "allOf" in cleaned and len(cleaned["allOf"]) == 1:
        inner = cleaned.pop("allOf")[0]
        cleaned = {**inner, **cleaned}
    return cleaned


_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def extract_json(text: str) -> Any:
    """Read JSON from a reply, tolerating code fences or text around the JSON."""
    text = text.strip()
    fenced = _FENCE.match(text)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except ValueError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])

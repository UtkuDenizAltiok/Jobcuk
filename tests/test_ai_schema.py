from typing import Literal

import pytest
from pydantic import BaseModel, Field

from jobcu.ai.schema import extract_json, strict_json_schema


class Language(BaseModel):
    name: str
    level: Literal["A1", "A2", "B1", "B2", "C1", "C2", "native"] | None


class Person(BaseModel):
    summary: str = Field(description="One sentence", max_length=200)
    years: float | None = Field(default=None, ge=0)
    languages: list[Language]


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def test_schema_is_self_contained_and_closed():
    schema = strict_json_schema(Person)
    text = str(schema)
    assert "$ref" not in text and "$defs" not in text
    for node in _walk(schema):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
        for banned in ("minimum", "maxLength", "title", "default"):
            assert banned not in node
    # Descriptions help the model and are kept.
    assert schema["properties"]["summary"]["description"] == "One sentence"


@pytest.mark.parametrize(
    "reply",
    [
        '{"ok": true}',
        '```json\n{"ok": true}\n```',
        'Here you go: {"ok": true} Hope this helps.',
    ],
)
def test_json_is_read_from_common_reply_shapes(reply):
    assert extract_json(reply) == {"ok": True}


def test_non_json_reply_raises():
    with pytest.raises(ValueError):
        extract_json("sorry, no")

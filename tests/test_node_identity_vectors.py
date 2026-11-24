"""The Python node-id validator accepts and rejects exactly what the shared vectors specify.

``tests/fixtures/node_identity_vectors.json`` is also consumed by ``tests/unit/node_identity_vectors.test.js``
against the frontend validator, so a target one side accepts is never one the other side rejects.
"""
import json
from pathlib import Path
from typing import Any

import pytest

from services.diagnostics.node_identity import valid_node_id

VECTORS = json.loads((Path(__file__).parent / "fixtures" / "node_identity_vectors.json").read_text(encoding="utf-8"))["vectors"]


def build(vector: dict) -> Any:
    kind = vector["kind"]
    if kind == "null":
        return None
    if kind == "list":
        return []
    if kind == "object":
        return {}
    if "repeat" in vector:
        return vector["repeat"] * vector["count"]
    return vector["value"]


def test_the_fixture_covers_both_outcomes_and_every_value_kind():
    assert {vector["kind"] for vector in VECTORS} == {"int", "str", "null", "bool", "float", "list", "object"}
    assert any(vector["accept"] for vector in VECTORS) and any(not vector["accept"] for vector in VECTORS)
    assert len({vector["name"] for vector in VECTORS}) == len(VECTORS)


@pytest.mark.parametrize("vector", VECTORS, ids=lambda vector: vector["name"])
def test_valid_node_id_matches_the_shared_vector(vector):
    value = build(vector)

    result = valid_node_id(value)

    if vector["accept"]:
        # The original scalar comes back untouched: same type, same value.
        assert result is not None and type(result) is type(value) and result == value
    else:
        assert result is None

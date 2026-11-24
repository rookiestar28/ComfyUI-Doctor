"""``host_node_registry()`` only reads what the host already loaded; it never imports a ``nodes`` module.

This lives outside the route harness on purpose: the harness blocks a top-level ``import nodes`` outright, so
inside it a lookup that imported ``nodes`` would fail quietly and look exactly like the correct behavior. The
reason to read ``sys.modules`` only is that the import path finds whichever ``nodes`` comes first, and this
package's own one-node ``nodes.py`` is importable under that name in tests and standalone runs.
"""
import sys
import types

import pytest

from services.diagnostics.known_nodes import HOST_REGISTRY_ANCHORS, host_node_registry

ANCHOR_REGISTRY_SOURCE = (
    "NODE_CLASS_MAPPINGS = {name: object for name in %r}\n" % (tuple(HOST_REGISTRY_ANCHORS),)
)


@pytest.fixture(autouse=True)
def _clean_nodes_module():
    saved = sys.modules.pop("nodes", None)
    try:
        yield
    finally:
        sys.modules.pop("nodes", None)
        if saved is not None:
            sys.modules["nodes"] = saved


def test_an_importable_nodes_module_is_not_imported_by_the_lookup(tmp_path, monkeypatch):
    (tmp_path / "nodes.py").write_text(ANCHOR_REGISTRY_SOURCE, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    assert host_node_registry() is None
    assert "nodes" not in sys.modules


def test_a_loaded_host_registry_is_returned_as_is():
    module = types.ModuleType("nodes")
    module.NODE_CLASS_MAPPINGS = {name: object for name in HOST_REGISTRY_ANCHORS}
    sys.modules["nodes"] = module

    assert host_node_registry() is module.NODE_CLASS_MAPPINGS


@pytest.mark.parametrize(
    "mapping",
    [None, [], "KSampler", 5, {}, {"KSampler": object}, {name: object for name in HOST_REGISTRY_ANCHORS[:-1]}],
    ids=repr,
)
def test_anything_that_is_not_an_anchored_mapping_is_not_a_registry(mapping):
    module = types.ModuleType("nodes")
    module.NODE_CLASS_MAPPINGS = mapping
    sys.modules["nodes"] = module

    assert host_node_registry() is None


def test_a_registry_attribute_that_raises_means_no_registry():
    class Broken(types.ModuleType):
        @property
        def NODE_CLASS_MAPPINGS(self):
            raise RuntimeError("host module is half initialized")

    sys.modules["nodes"] = Broken("nodes")

    assert host_node_registry() is None

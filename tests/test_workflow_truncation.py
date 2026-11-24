"""
Tests for R8: Smart Workflow Truncation
"""
import unittest
import sys
import os
import json

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from truncate_workflow import _get_priority_nodes, truncate_workflow_smart


class TestWorkflowTruncation(unittest.TestCase):
    """Tests for R8 smart workflow truncation."""
    
    def test_small_workflow_unchanged(self):
        """Small workflows should pass through unchanged."""
        small_workflow = json.dumps({"nodes": [{"id": 1, "type": "KSampler"}]})
        result, meta = truncate_workflow_smart(small_workflow, max_chars=1000)
        
        self.assertEqual(meta["truncation_method"], "none")
        self.assertEqual(result, small_workflow)
    
    def test_empty_workflow(self):
        """Empty workflow should return empty string."""
        result, meta = truncate_workflow_smart("", max_chars=100)
        
        self.assertEqual(result, "")
        self.assertEqual(meta["truncation_method"], "none")
    
    def test_large_workflow_truncated(self):
        """Large workflows should be truncated."""
        # Create a large workflow with many nodes
        nodes = [{"id": i, "type": f"Node{i}", "properties": {"data": "x" * 100}} for i in range(50)]
        large_workflow = json.dumps({"nodes": nodes})
        
        result, meta = truncate_workflow_smart(large_workflow, max_chars=500)
        
        self.assertLess(len(result), len(large_workflow))
        self.assertIn(meta["truncation_method"], ["property_pruning", "node_removal", "char_slice"])
        self.assertIn("original_nodes", meta)
    
    def test_returns_valid_json_or_readable_string(self):
        """Output should be valid JSON or at least readable."""
        nodes = [{"id": i, "type": f"Node{i}"} for i in range(100)]
        workflow = json.dumps({"nodes": nodes})
        
        result, meta = truncate_workflow_smart(workflow, max_chars=200)
        
        # Should either be valid JSON or readable text
        try:
            json.loads(result)
            valid_json = True
        except json.JSONDecodeError:
            valid_json = False
            # If not valid JSON, should at least have truncation marker
            self.assertIn("truncated", result.lower())
    
    def test_preserves_error_node(self):
        """Error node should be preserved when specified."""
        nodes = [
            {"id": "1", "type": "NodeA", "inputs": {}},
            {"id": "2", "type": "NodeB", "inputs": {"a": ["1", 0]}},
            {"id": "3", "type": "NodeC", "inputs": {"b": ["2", 0]}},
            {"id": "4", "type": "NodeD", "inputs": {}},
            {"id": "5", "type": "NodeE", "inputs": {}},
        ]
        # Add some bulk to force truncation
        for node in nodes:
            node["properties"] = {"large_data": "x" * 500}
        
        workflow = json.dumps({"nodes": nodes})
        
        # Truncate with error node = "3"
        result, meta = truncate_workflow_smart(workflow, error_node_id="3", max_chars=800)
        
        # Check that error node 3 is preserved (if node_removal was used)
        if meta["truncation_method"] == "node_removal":
            self.assertTrue(meta.get("error_node_preserved", True))
    
    def test_invalid_json_fallback(self):
        """Invalid JSON should fall back to character truncation."""
        invalid_workflow = "This is not JSON at all, just plain text" * 100
        
        result, meta = truncate_workflow_smart(invalid_workflow, max_chars=100)
        
        self.assertEqual(meta["truncation_method"], "char_slice")
        self.assertLessEqual(len(result), 100)
    
    def test_metadata_contains_required_fields(self):
        """Metadata should contain required fields."""
        workflow = json.dumps({"nodes": [{"id": 1}]})
        _, meta = truncate_workflow_smart(workflow)
        
        self.assertIn("truncation_method", meta)
        self.assertIn("original_length", meta)
    
    def test_property_pruning_preserves_node_count(self):
        """Property pruning should keep all nodes."""
        nodes = [
            {"id": 1, "type": "A", "widgets_values": [1, 2, 3], "pos": [0, 0], "size": [100, 100]},
            {"id": 2, "type": "B", "widgets_values": [4, 5, 6], "pos": [100, 0], "size": [100, 100]},
        ]
        workflow = json.dumps({"nodes": nodes})
        
        result, meta = truncate_workflow_smart(workflow, max_chars=200)
        
        if meta["truncation_method"] == "property_pruning":
            self.assertEqual(meta["original_nodes"], meta["kept_nodes"])

    def test_execution_id_error_node_matches_local_node_id(self):
        """Execution IDs from subgraphs should still preserve the target node."""
        nodes = []
        for i in range(1, 8):
            nodes.append({
                "id": str(i),
                "type": f"Node{i}",
                "inputs": {"x": [str(i - 1), 0]} if i > 1 else {},
                "properties": {"large_data": "x" * 400},
            })
        workflow = json.dumps({"nodes": nodes, "links": []})

        result, meta = truncate_workflow_smart(
            workflow,
            error_node_id="65:70:6",
            max_chars=700,
        )

        self.assertEqual(meta["truncation_method"], "node_removal")
        self.assertTrue(meta.get("error_node_preserved"))
        parsed = json.loads(result)
        self.assertTrue(any(str(node.get("id")) == "6" for node in parsed["nodes"]))

    def test_ui_workflow_pruning_preserves_metadata_and_filters_links(self):
        """UI-format workflow pruning should preserve top-level metadata and valid links."""
        nodes = [
            {"id": "1", "type": "Loader", "inputs": {}, "properties": {"blob": "x" * 400}},
            {"id": "2", "type": "KSampler", "inputs": {"model": ["1", 0]}, "properties": {"blob": "y" * 400}},
            {"id": "3", "type": "SaveImage", "inputs": {"images": ["2", 0]}, "properties": {"blob": "z" * 400}},
            {"id": "4", "type": "Unused", "inputs": {}, "properties": {"blob": "w" * 400}},
        ]
        workflow = json.dumps({
            "nodes": nodes,
            "links": [
                [1, "1", 0, "2", 0, "MODEL"],
                [2, "2", 0, "3", 0, "IMAGE"],
                [3, "4", 0, "3", 1, "IMAGE"],
            ],
            "groups": [{"title": "Subgraph Host"}],
            "extra": {"groupNodes": {"Demo": {"version": 1}}},
        })

        result, meta = truncate_workflow_smart(workflow, error_node_id="2", max_chars=900)

        self.assertIn(meta["truncation_method"], {"property_pruning", "node_removal"})
        parsed = json.loads(result)
        self.assertIn("groups", parsed)
        self.assertIn("extra", parsed)
        self.assertEqual(parsed["groups"][0]["title"], "Subgraph Host")
        kept_ids = {str(node["id"]) for node in parsed["nodes"]}
        for link in parsed["links"]:
            self.assertIn(str(link[1]), kept_ids)
            self.assertIn(str(link[3]), kept_ids)

        if meta["truncation_method"] == "node_removal":
            self.assertNotIn("4", kept_ids)



PROMPT_TEXT = "masterpiece, best quality, a detailed portrait of a person standing in a field of flowers"


def _host_node(node_id, node_type, widgets, names, inputs, outputs):
    """A node as the host frontend serializes it: positional `widgets_values` next to name-keyed `widgets_values_named`."""
    node = {
        "id": node_id, "type": node_type, "pos": [100.0 * node_id, 80.0], "size": [315, 262],
        "flags": {}, "order": node_id, "mode": 0, "inputs": inputs, "outputs": outputs,
        "properties": {"Node name for S&R": node_type}, "widgets_values": widgets,
    }
    if names is not None:
        node["widgets_values_named"] = dict(zip(names, widgets))
    return node


def _host_workflow(sections, with_named):
    """Repeat a seven-node SDXL-like chain; node ids and link ids are unique per section."""
    nodes, links, next_id, link_id = [], [], 1, 1

    def names(*values):
        return values if with_named else None

    for _ in range(sections):
        ck, pos, neg, lat, ks, dec, sv = range(next_id, next_id + 7)
        next_id += 7
        lid = link_id
        nodes.append(_host_node(ck, "CheckpointLoaderSimple", ["sd_xl_base_1.0.safetensors"], names("ckpt_name"), [], [
            {"name": "MODEL", "type": "MODEL", "links": [lid]}, {"name": "CLIP", "type": "CLIP", "links": [lid + 1]},
            {"name": "VAE", "type": "VAE", "links": [lid + 2]}]))
        nodes.append(_host_node(pos, "CLIPTextEncode", [PROMPT_TEXT], names("text"),
                                [{"name": "clip", "type": "CLIP", "link": lid + 1}],
                                [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [lid + 3]}]))
        nodes.append(_host_node(neg, "CLIPTextEncode", ["blurry, low quality, watermark"], names("text"),
                                [{"name": "clip", "type": "CLIP", "link": lid + 1}],
                                [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [lid + 4]}]))
        nodes.append(_host_node(lat, "EmptyLatentImage", [1024, 1024, 1], names("width", "height", "batch_size"), [],
                                [{"name": "LATENT", "type": "LATENT", "links": [lid + 5]}]))
        nodes.append(_host_node(
            ks, "KSampler", [123456789, "randomize", 30, 7.5, "euler", "normal", 1.0],
            names("seed", "control_after_generate", "steps", "cfg", "sampler_name", "scheduler", "denoise"),
            [{"name": "model", "type": "MODEL", "link": lid}, {"name": "positive", "type": "CONDITIONING", "link": lid + 3},
             {"name": "negative", "type": "CONDITIONING", "link": lid + 4}, {"name": "latent_image", "type": "LATENT", "link": lid + 5}],
            [{"name": "LATENT", "type": "LATENT", "links": [lid + 6]}]))
        nodes.append(_host_node(dec, "VAEDecode", [], names(),
                                [{"name": "samples", "type": "LATENT", "link": lid + 6}, {"name": "vae", "type": "VAE", "link": lid + 2}],
                                [{"name": "IMAGE", "type": "IMAGE", "links": [lid + 7]}]))
        nodes.append(_host_node(sv, "SaveImage", ["ComfyUI"], names("filename_prefix"),
                                [{"name": "images", "type": "IMAGE", "link": lid + 7}], []))
        for offset, (origin, target) in enumerate(
            [(ck, ks), (ck, pos), (ck, dec), (pos, ks), (neg, ks), (lat, ks), (ks, dec), (dec, sv)]
        ):
            links.append([lid + offset, origin, 0, target, 0, "T"])
        link_id += 8
    return {"last_node_id": next_id, "last_link_id": link_id, "nodes": nodes, "links": links, "version": 0.4}


def _ui_chain(count, pad=300):
    """UI format: `inputs` is a list of slot dicts and connections live only in the top-level `links` rows."""
    nodes, links = [], []
    for i in range(1, count + 1):
        nodes.append({
            "id": i, "type": f"Step{i}",
            "inputs": [{"name": "in", "type": "X", "link": i - 1}] if i > 1 else [],
            "outputs": [{"name": "out", "type": "X", "links": [i]}] if i < count else [],
            "properties": {"note": "n" * pad},
        })
        if i > 1:
            links.append([i - 1, i - 1, 0, i, 0, "X"])
    return {"nodes": nodes, "links": links, "version": 0.4}


def _api_chain(count, pad=300):
    """API format twin of `_ui_chain`: connections live in each node's `inputs` dict."""
    return {"nodes": [
        {"id": str(i), "type": f"Step{i}", "inputs": {"x": [str(i - 1), 0]} if i > 1 else {}, "properties": {"note": "n" * pad}}
        for i in range(1, count + 1)
    ]}


class TestHostSerializedWorkflowTruncation(unittest.TestCase):
    """Workflows as serialized by the host frontend: named widget copies and list-shaped inputs."""

    PRUNED_NODE_KEYS = {"id", "type", "inputs", "outputs", "properties"}

    def _run(self, sections, with_named, max_chars, error_node=5):
        workflow = _host_workflow(sections, with_named)
        return truncate_workflow_smart(json.dumps(workflow, ensure_ascii=False), str(error_node), max_chars=max_chars)

    def test_named_copy_does_not_change_the_pruning_strategy(self):
        # 14 nodes at the analyze budget and 7 nodes at the chat budget fit property pruning only
        # when the named copy is pruned together with the positional one.
        for sections, max_chars in ((2, 4000), (1, 2000)):
            with self.subTest(nodes=sections * 7, max_chars=max_chars):
                plain_out, plain = self._run(sections, False, max_chars)
                named_out, named = self._run(sections, True, max_chars)
                self.assertEqual(plain["truncation_method"], "property_pruning")
                self.assertEqual(named["truncation_method"], "property_pruning")
                self.assertEqual(named["kept_nodes"], plain["kept_nodes"])
                self.assertEqual(named["kept_nodes"], sections * 7)
                self.assertEqual(named_out, plain_out)

    def test_named_copy_never_survives_property_pruning_or_node_removal(self):
        for sections in (1, 2, 3, 4, 6):
            for max_chars in (2000, 4000):
                with self.subTest(sections=sections, max_chars=max_chars):
                    out, meta = self._run(sections, True, max_chars)
                    if meta["truncation_method"] not in {"property_pruning", "node_removal"}:
                        continue
                    self.assertNotIn("widgets_values_named", out)
                    for node in json.loads(out)["nodes"]:
                        self.assertLessEqual(set(node), self.PRUNED_NODE_KEYS)

    def test_positional_only_workflows_keep_their_strategy(self):
        out, meta = self._run(2, False, 4000)
        self.assertEqual((meta["truncation_method"], meta["kept_nodes"]), ("property_pruning", 14))
        self.assertLessEqual(len(out), 4000)

    def test_ui_neighbors_match_the_api_format_twin(self):
        for hops in (0, 1, 2):
            with self.subTest(hops=hops):
                self.assertEqual(
                    _get_priority_nodes(_ui_chain(12), "6", hops),
                    _get_priority_nodes(_api_chain(12), "6", hops),
                )

    def test_ui_neighbors_follow_link_rows_in_both_directions(self):
        self.assertEqual(_get_priority_nodes(_ui_chain(12), "6", 0), {"6"})
        self.assertEqual(_get_priority_nodes(_ui_chain(12), "6", 1), {"5", "6", "7"})

    def test_ui_workflow_node_removal_keeps_the_error_neighborhood(self):
        workflow = _ui_chain(12)
        text = json.dumps(workflow)
        result, meta = truncate_workflow_smart(text, "6", max_chars=2000, max_hops=1)

        self.assertEqual(meta["truncation_method"], "node_removal")
        self.assertTrue(meta["error_node_preserved"])
        self.assertLessEqual(len(result), 2000)
        parsed = json.loads(result)
        kept = {str(node["id"]) for node in parsed["nodes"]}
        self.assertEqual(kept, {"5", "6", "7"})
        self.assertEqual(meta["kept_nodes"], 3)
        self.assertEqual(meta["original_nodes"], 12)
        for link in parsed["links"]:
            self.assertIn(str(link[1]), kept)
            self.assertIn(str(link[3]), kept)
        self.assertEqual(len(parsed["links"]), 2)

    def test_api_format_neighbors_are_unchanged(self):
        self.assertEqual(_get_priority_nodes(_api_chain(5), "3", 1), {"2", "3", "4"})
        self.assertEqual(_get_priority_nodes(_api_chain(5), "3", 0), {"3"})

    def test_malformed_link_rows_never_raise_and_fall_back_to_the_error_node(self):
        malformed = (
            "oops", {"a": 1}, 7, [None], [[]], [[1]], [[1, 2]], [[1, 2, 3, 4]], [["a", "b", "c", "d"]],
            [[1, "99", 0, "6", 0, "X"]],  # unknown origin
            [[1, "6", 0, "99", 0, "X"]],  # unknown target
            [[1, "6", 0, "6", 0, "X"]],  # self link
            [{"id": 1}], [None, None], [[1, [], 0, {}, 0, "X"]],
        )
        for links in malformed:
            with self.subTest(links=repr(links)):
                workflow = _ui_chain(12)
                workflow["links"] = links
                self.assertEqual(_get_priority_nodes(workflow, "6", 2), {"6"})
        absent = _ui_chain(12)
        del absent["links"]
        self.assertEqual(_get_priority_nodes(absent, "6", 2), {"6"})

    def test_duplicate_and_extra_link_rows_are_harmless(self):
        workflow = _ui_chain(12)
        workflow["links"] = workflow["links"] + workflow["links"] + [[99, "6", 0, "6", 0, "X"], ["x"]]
        self.assertEqual(_get_priority_nodes(workflow, "6", 1), {"5", "6", "7"})

    def test_api_format_nodes_ignore_top_level_link_rows(self):
        # Dict-input (API format) nodes keep their own connections as the only authority.
        workflow = _api_chain(12)
        workflow["links"] = [[1, "11", 0, "6", 0, "X"]]
        self.assertEqual(_get_priority_nodes(workflow, "6", 1), {"5", "6", "7"})

    def test_link_parsing_does_not_mutate_the_workflow(self):
        import copy
        workflow = _ui_chain(12)
        original = copy.deepcopy(workflow)
        _get_priority_nodes(workflow, "6", 2)
        truncate_workflow_smart(json.dumps(workflow), "6", max_chars=2000)
        self.assertEqual(workflow, original)

    def test_no_error_node_still_keeps_the_first_twenty_nodes(self):
        result, meta = truncate_workflow_smart(json.dumps(_ui_chain(30)), None, max_chars=6000)
        self.assertEqual(meta["truncation_method"], "node_removal")
        self.assertEqual(meta["kept_nodes"], 20)
        self.assertLessEqual(len(result), 6000)

    def test_metadata_contract_keys_are_unchanged(self):
        _, meta = truncate_workflow_smart(json.dumps(_ui_chain(12)), "6", max_chars=2000, max_hops=1)
        self.assertEqual(
            set(meta),
            {"truncation_method", "original_length", "truncated_length", "original_nodes", "kept_nodes", "error_node_preserved"},
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)

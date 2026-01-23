
import pytest
from unittest.mock import patch, MagicMock
from services.intent.loader import load_intents
from services.intent import IntentScorer, SignalExtractor, _sanitize_evidence_string

# ============================================================================
# P3 Follow-up: Dedicated Sanitization Unit Tests
# ============================================================================

class TestSanitizationHelper:
    """Test the _sanitize_evidence_string function directly."""

    def test_basic_strings(self):
        assert _sanitize_evidence_string("") == ""
        assert _sanitize_evidence_string("Hello World") == "Hello World"
        assert _sanitize_evidence_string("Node: KSampler") == "Node: KSampler"

    def test_length_capping(self):
        # 120 chars max
        long = "A" * 200
        sanitized = _sanitize_evidence_string(long)
        assert len(sanitized) <= 123
        assert sanitized.endswith("...")

    def test_windows_paths(self):
        # drive letter + colon + backslash
        assert "[REDACTED]" in _sanitize_evidence_string(r"C:\Users\Secret\file.py")
        assert "[REDACTED]" in _sanitize_evidence_string(r"Loading from D:\Models\Checkpoints\sd_xl.safetensors")
        # Mixed content - use parens to delimit to verify boundary
        res = _sanitize_evidence_string(r"Error at (C:\Windows\System32\driver.sys) failed")
        assert "Error at ([REDACTED]) failed" in res

    def test_unix_paths(self):
        # common roots
        assert "[REDACTED]" in _sanitize_evidence_string("/home/user/.ssh/id_rsa")
        assert "[REDACTED]" in _sanitize_evidence_string("/var/log/syslog")
        # Mixed
        res = _sanitize_evidence_string("Config: /etc/comfy/secret.json loaded")
        assert "Config: [REDACTED] loaded" in res

    def test_bearer_tokens(self):
        token = "Bearer sk-1234567890abcdef1234567890"
        assert _sanitize_evidence_string(token) == "Bearer [REDACTED]"
        
        mixed = "Auth failed for Bearer sk-123... retrying"
        res = _sanitize_evidence_string(mixed)
        assert "Auth failed for Bearer [REDACTED] retrying" in res

    def test_api_keys(self):
        # OpenAI sk-
        sk = "sk-7n9283749283749283749283749283749283"
        assert "[REDACTED]" in _sanitize_evidence_string(f"Key {sk} invalid")
        
        # Google AIza
        aiza = "AIzaSyD-1234567890abcdef1234567890abcde"
        assert "[REDACTED]" in _sanitize_evidence_string(f"Google key {aiza} used")
        
        # HF
        hf = "hf_1234567890abcdef1234567890abcdef"
        assert "[REDACTED]" in _sanitize_evidence_string(f"HuggingFace {hf} token")
        
    def test_false_positives(self):
        # Should NOT redact regular text
        assert _sanitize_evidence_string("Basic text is safe") == "Basic text is safe"
        assert _sanitize_evidence_string("Node ID: 12345") == "Node ID: 12345"
        assert _sanitize_evidence_string("sk-short") == "sk-short"  # Too short for key regex
        assert _sanitize_evidence_string("C: is a drive") == "C: is a drive" # No backslash sequence

# Mock Workflow
MOCK_WORKFLOW_TXT2IMG = {
    "nodes": [
        {"id": 1, "type": "KSampler"},
        {"id": 2, "type": "CLIPTextEncode"},
        {"id": 3, "type": "EmptyLatentImage"},
        {"id": 4, "type": "VAEDecode"},
        {"id": 5, "type": "SaveImage"}
    ],
    "links": [
        [1, 3, 0, 1, 3, "LATENT"], # EmptyLatent -> KSampler
        [2, 2, 0, 1, 1, "CONDITIONING"], # CLIPText -> KSampler
        [3, 1, 0, 4, 0, "LATENT"], # KSampler -> VAEDecode
    ]
}

MOCK_WORKFLOW_IMG2IMG = {
    "nodes": [
        {"id": 1, "type": "KSampler"},
        {"id": 2, "type": "LoadImage"},
        {"id": 3, "type": "VAEEncode"},
        {"id": 4, "type": "VAEDecode"}
    ],
    "links": []
}

class TestIntentLoader:
    def test_load_intents_defaults(self):
        """Test fallback behavior if file missing (or just check builtin load)."""
        # Since we created the file, this should load actual JSON or fallback
        intents = load_intents()
        assert "txt2img" in intents
        assert "img2img" in intents

    @patch("services.intent.loader.os.path.exists")
    def test_load_fallback(self, mock_exists):
        """Force fallback by mocking file non-existence."""
        mock_exists.return_value = False
        intents = load_intents()
        assert "txt2img" in intents
        # Fallback might have fewer intents or just txt2img
        assert len(intents) >= 1

class TestSignalExtractor:
    def test_extraction_basic(self):
        extractor = SignalExtractor()
        signals = extractor.extract(MOCK_WORKFLOW_TXT2IMG)
        
        sig_ids = [s.signal_id for s in signals]
        assert "node_type.KSampler" in sig_ids
        assert "node_type.CLIPTextEncode" in sig_ids
        # Check edge
        # Links: 1(EmptyLatent)->1(KSampler)
        # EmptyLatent ID=3, KSampler ID=1
        # link[1]=3, link[3]=1
        # edge.EmptyLatentImage_KSampler
        assert "edge.EmptyLatentImage_KSampler" in sig_ids

    def test_malformed_workflow(self):
        extractor = SignalExtractor()
        signals = extractor.extract({"nodes": "invalid"})
        assert len(signals) == 0

    def test_extraction_dict_nodes(self):
        """Test extraction from API-format workflow (dict of nodes)."""
        workflow = {
            "nodes": {
                "1": {"id": 1, "type": "KSampler"},
                "2": {"id": 2, "type": "CLIPTextEncode"}
            }
        }
        extractor = SignalExtractor()
        signals = extractor.extract(workflow)
        sig_ids = [s.signal_id for s in signals]
        assert "node_type.KSampler" in sig_ids
        assert "node_type.CLIPTextEncode" in sig_ids

    def test_evidence_sanitization(self):
        """Test that evidence strings are capped and sanitized."""
        extractor = SignalExtractor()

        # 1. Length capping
        long_type = "A" * 200
        workflow = {"nodes": [{"id": 1, "type": long_type}]}
        signals = extractor.extract(workflow)
        sig = next(s for s in signals if s.signal_id.startswith("node_type."))
        assert len(sig.explain) <= 123
        assert sig.explain.endswith("...")

        # 2. Path Redaction (Windows)
        win_path = r"C:\Users\Secret\User\ComfyUI\custom_nodes\test.py"
        # We simulate this showing up in 'type' or similar field that gets into explain
        # Note: 'type' is part of signal_id usually, but let's check explain construction.
        # But wait, node type is usually a short string. Let's force a scenario where explain uses unsanitized input.
        # SignalExtractor uses: explain=f"Node type '{node_type}' present"
        # So we inject the path into node_type
        workflow_win = {"nodes": [{"id": 2, "type": win_path}]}
        signals_win = extractor.extract(workflow_win)
        # signal_id will contain the path (it's not sanitized for ID uniqueness), but explain MUST be.
        sig_win = next(s for s in signals_win if s.signal_id.startswith("node_type."))
        assert "[REDACTED]" in sig_win.explain
        assert "Secret" not in sig_win.explain

        # 3. Path Redaction (Unix)
        unix_path = "/home/deploy/api_keys/config.json"
        workflow_unix = {"nodes": [{"id": 3, "type": unix_path}]}
        signals_unix = extractor.extract(workflow_unix)
        sig_unix = next(s for s in signals_unix if s.signal_id.startswith("node_type."))
        assert "[REDACTED]" in sig_unix.explain
        assert "deploy" not in sig_unix.explain

        # 4. Bearer Token
        bearer = "Bearer sk-1234567890abcdef"
        workflow_token = {"nodes": [{"id": 4, "type": bearer}]}
        signals_token = extractor.extract(workflow_token)
        sig_token = next(s for s in signals_token if s.signal_id.startswith("node_type."))
        assert "Bearer [REDACTED]" in sig_token.explain
        assert "sk-12345" not in sig_token.explain

class TestIntentScorer:
    def test_score_txt2img(self):
        import asyncio
        async def _run():
            scorer = IntentScorer()
            # Mock extractor logic by passing workflow that produces known signals
            signature = await scorer.compute(MOCK_WORKFLOW_TXT2IMG, "hash123")
            
            assert len(signature.top_intents) > 0
            top = signature.top_intents[0]
            assert top.intent_id == "txt2img"
            assert top.confidence > 0.5
            assert top.stage == "generation"
        asyncio.run(_run())

    def test_score_img2img(self):
        import asyncio
        async def _run():
            scorer = IntentScorer()
            signature = await scorer.compute(MOCK_WORKFLOW_IMG2IMG, "hash456")
            
            # img2img requires LoadImage + KSampler + VAEEncode(positive)
            # Our mock has them.
            top_ids = [i.intent_id for i in signature.top_intents]
            assert "img2img" in top_ids
        asyncio.run(_run())

    def test_score_missing_requirements(self):
        import asyncio
        async def _run():
            scorer = IntentScorer()
            # Workflow with just KSampler, missing CLIPTextEncode (required for txt2img)
            # and missing LoadImage (required for img2img)
            workflow = {
                "nodes": [{"id": 1, "type": "KSampler"}]
            }
            signature = await scorer.compute(workflow, "hash789")
            
            # Should NOT match txt2img
            top_ids = [i.intent_id for i in signature.top_intents]
            assert "txt2img" not in top_ids
        asyncio.run(_run())

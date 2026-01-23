
import pytest
from unittest.mock import patch, MagicMock
from services.intent.loader import load_intents
from services.intent import IntentScorer, SignalExtractor

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
        long_type = "A" * 200
        workflow = {
            "nodes": [{"id": 1, "type": long_type}]
        }
        extractor = SignalExtractor()
        signals = extractor.extract(workflow)
        
        # Should have node_type.AAAA...
        # Note: signal_id is NOT sanitized (for matching), but explain IS.
        sig = next(s for s in signals if s.signal_id.startswith("node_type."))
        # Check explain string
        assert len(sig.explain) <= 123  # 120 + "..."
        assert sig.explain.endswith("...")

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

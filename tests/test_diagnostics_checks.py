"""
Unit tests for F14 Diagnostics Checks.
Tests privacy_security and runtime_performance heuristics.
Uses unittest.IsolatedAsyncioTestCase for async compatibility.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from services.diagnostics.checks import model_assets, privacy_security, runtime_performance
from services.diagnostics.models import (
    HealthCheckRequest,
    IssueSeverity,
    IssueCategory,
    DiagnosticsScope
)

class TestPrivacySecurityChecks(unittest.IsolatedAsyncioTestCase):
    
    async def test_privacy_security_check_safe_local(self):
        """Test safe configuration: privacy=none with local provider."""
        # Mock settings
        with patch("services.diagnostics.checks.privacy_security._get_settings_info") as mock_settings:
            mock_settings.return_value = {
                "api_keys_present": {},
                "privacy_mode": "none"
            }
            
            workflow = {
                "extra": {
                    "doctor_metadata": {
                        "privacy_mode": "none",
                        "base_url": "http://localhost:1234/v1"  # LMStudio
                    }
                }
            }
            
            request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
            issues = await privacy_security.check_privacy_security(workflow, request)
            
            # Should have INFO issue for local usage, but no warnings
            # Debug info if fails
            issue_ids = [i.issue_id for i in issues]
            self.assertEqual(len(issues), 1, f"Expected 1 issue, found {len(issues)}: {issue_ids}")
            self.assertEqual(issues[0].severity, IssueSeverity.INFO)
            self.assertIn("Privacy Mode Disabled", issues[0].title)

    async def test_privacy_security_check_unsafe_remote(self):
        """Test unsafe configuration: privacy=none with remote provider."""
        with patch("services.diagnostics.checks.privacy_security._get_settings_info") as mock_settings:
            mock_settings.return_value = {
                "api_keys_present": {"OpenAI": True},
                "privacy_mode": "none"
            }
            
            workflow = {
                "extra": {
                    "doctor_metadata": {
                        "privacy_mode": "none",
                        "base_url": "https://api.openai.com/v1"
                    }
                }
            }
            
            request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
            issues = await privacy_security.check_privacy_security(workflow, request)
            
            # Should have CRITICAL issue
            crit_issues = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
            self.assertEqual(len(crit_issues), 1, f"Expected 1 critical issue, found {len(crit_issues)}")
            self.assertIn("Privacy Mode Disabled", crit_issues[0].title)

    async def test_privacy_security_missing_api_key(self):
        """Test missing API key for remote provider."""
        with patch("services.diagnostics.checks.privacy_security._get_settings_info") as mock_settings:
            mock_settings.return_value = {
                "api_keys_present": {"OpenAI": False},  # Key missing!
                "privacy_mode": "basic"
            }
            
            workflow = {
                "extra": {
                    "doctor_metadata": {
                        "privacy_mode": "basic",
                        "base_url": "https://api.openai.com/v1"
                    }
                }
            }
            
            request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
            issues = await privacy_security.check_privacy_security(workflow, request)
            
            # Should have WARNING for missing key
            warn_issues = [i for i in issues if i.severity == IssueSeverity.WARNING]
            self.assertEqual(len(warn_issues), 1, f"Expected 1 warning, found {len(warn_issues)}")
            self.assertIn("API Key Not Configured", warn_issues[0].title)


class TestRuntimePerformanceChecks(unittest.IsolatedAsyncioTestCase):

    async def test_runtime_perf_extreme_resolution(self):
        """Test extreme resolution warnings."""
        with patch("services.diagnostics.checks.runtime_performance._get_env_info") as mock_env:
            mock_env.return_value = {
                "gpu_memory_gb": 24.0,
                "cuda_available": True
            }
            
            # 8K resolution (approx 8192x8192) -> Extreme
            workflow = {
                "nodes": [
                    {
                        "type": "EmptyLatentImage",
                        "widgets_values": [8192, 8192, 1]
                    }
                ]
            }
            
            request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
            issues = await runtime_performance.check_runtime_performance(workflow, request)
            
            # Should find extreme resolution warning
            res_issues = [i for i in issues if "Extreme Resolution" in i.title]
            self.assertEqual(len(res_issues), 1)
            self.assertEqual(res_issues[0].severity, IssueSeverity.WARNING)

    async def test_runtime_perf_vram_risk_critical(self):
        """Test VRAM OOM risk estimation."""
        with patch("services.diagnostics.checks.runtime_performance._get_env_info") as mock_env:
            # Low VRAM environment
            mock_env.return_value = {
                "gpu_memory_gb": 4.0,
                "cuda_available": True
            }
            
            # Large batch on 4GB VRAM -> OOM risk
            # 1024x1024 batch 4
            workflow = {
                "nodes": [
                    {
                        "type": "EmptyLatentImage",
                        "widgets_values": [1024, 1024, 4]
                    }
                ]
            }
            
            request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
            issues = await runtime_performance.check_runtime_performance(workflow, request)
            
            # Should find VRAM risk warning
            oom_issues = [i for i in issues if "Out-of-Memory" in i.title]
            self.assertEqual(len(oom_issues), 1)
            self.assertEqual(oom_issues[0].severity, IssueSeverity.WARNING)
            self.assertIn("exceeds available", oom_issues[0].summary)

    async def test_runtime_perf_large_batch(self):
        """Test batch size warnings."""
        with patch("services.diagnostics.checks.runtime_performance._get_env_info") as mock_env:
            mock_env.return_value = {"gpu_memory_gb": 24.0, "cuda_available": True}
            
            # Batch 64 -> Critical batch size
            workflow = {
                "nodes": [
                    {
                        "type": "EmptyLatentImage",
                        "widgets_values": [512, 512, 64]
                    }
                ]
            }
            
            request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
            issues = await runtime_performance.check_runtime_performance(workflow, request)
            
            batch_issues = [i for i in issues if "Batch Size" in i.title]
            self.assertEqual(len(batch_issues), 1)


class TestModelAssetsChecks(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        model_assets._clear_path_cache()

    def tearDown(self):
        model_assets._clear_path_cache()

    def test_model_assets_discovers_current_host_folders(self):
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)

            def get_folder_paths(folder_name):
                if folder_name in {"geometry_estimation", "detection"}:
                    return [str(root / folder_name)]
                return []

            folder_paths = SimpleNamespace(
                get_folder_paths=get_folder_paths,
                get_input_directory=lambda: str(root / "input"),
                get_output_directory=lambda: str(root / "output"),
            )

            with patch.dict(sys.modules, {"folder_paths": folder_paths}):
                paths = model_assets._get_comfy_model_paths()

            self.assertEqual(paths["geometry_estimation"], [root / "geometry_estimation"])
            self.assertEqual(paths["detection"], [root / "detection"])

    async def test_model_assets_geometry_reference_searches_geometry_folder(self):
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            geometry_dir = root / "models" / "geometry_estimation"
            geometry_dir.mkdir(parents=True)
            (geometry_dir / "moge_v2.safetensors").write_bytes(b"x")

            with patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value={
                    "checkpoints": [],
                    "geometry_estimation": [geometry_dir],
                    "detection": [],
                    "input": [],
                    "output": [],
                },
            ):
                workflow = {"nodes": [{"id": 10, "type": "LoadMoGeModel", "widgets_values": ["moge_v2.safetensors"]}]}
                request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
                issues = await model_assets.check_model_assets(workflow, request)

            self.assertEqual(issues, [])

    async def test_model_assets_detection_reference_searches_detection_folder(self):
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            detection_dir = root / "models" / "detection"
            detection_dir.mkdir(parents=True)
            (detection_dir / "mediapipe_face_landmarker.safetensors").write_bytes(b"x")

            with patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value={
                    "checkpoints": [],
                    "geometry_estimation": [],
                    "detection": [detection_dir],
                    "input": [],
                    "output": [],
                },
            ):
                workflow = {
                    "nodes": [
                        {
                            "id": 11,
                            "type": "LoadMediaPipeFaceLandmarker",
                            "widgets_values": ["mediapipe_face_landmarker.safetensors"],
                        }
                    ]
                }
                request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
                issues = await model_assets.check_model_assets(workflow, request)

            self.assertEqual(issues, [])

    async def test_model_assets_old_host_does_not_fallback_geometry_to_checkpoints(self):
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            checkpoint_dir = root / "private" / "models" / "checkpoints"
            checkpoint_dir.mkdir(parents=True)
            (checkpoint_dir / "moge_v2.safetensors").write_bytes(b"x")

            with patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value={
                    "checkpoints": [checkpoint_dir],
                    "geometry_estimation": [],
                    "detection": [],
                    "input": [],
                    "output": [],
                },
            ):
                workflow = {"nodes": [{"id": 12, "type": "LoadMoGeModel", "widgets_values": ["moge_v2.safetensors"]}]}
                request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
                issues = await model_assets.check_model_assets(workflow, request)

            self.assertEqual(len(issues), 1)
            self.assertIn("Searched in: geometry_estimation folders", issues[0].evidence)
            evidence_text = "\n".join([issues[0].summary, *issues[0].evidence])
            self.assertIn("moge_v2.safetensors", evidence_text)
            self.assertNotIn(temp_root, evidence_text)
            self.assertNotIn("private", evidence_text)

    def test_model_assets_preserves_existing_category_detection(self):
        cases = [
            ("CheckpointLoaderSimple", "dreamshaper.safetensors", "checkpoints"),
            ("VAELoader", "anime_vae.safetensors", "vae"),
            ("LoraLoader", "detail_lora.safetensors", "loras"),
            ("ControlNetLoader", "pose_controlnet.safetensors", "controlnet"),
            ("CLIPLoader", "clip_l.safetensors", "clip"),
            ("UpscaleModelLoader", "realesrgan.safetensors", "upscale_models"),
            ("EmbeddingLoader", "bad-hands.pt", "embeddings"),
            ("LoadImage", "example.png", "input"),
        ]

        for node_type, filename, expected in cases:
            with self.subTest(node_type=node_type):
                self.assertEqual(model_assets._determine_asset_category(node_type, filename), expected)

if __name__ == '__main__':
    unittest.main(verbosity=2)

"""
Unit tests for F14 Diagnostics Checks.
Tests privacy_security and runtime_performance heuristics.
Uses unittest.IsolatedAsyncioTestCase for async compatibility.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, mock_open
from services.diagnostics.checks import (
    env_deps,
    model_assets,
    privacy_security,
    runtime_performance,
)
from services.diagnostics.models import (
    HealthReport,
    HealthCheckRequest,
    IssueSeverity,
    IssueCategory,
    DiagnosticsScope
)
from services.diagnostics.runner import DiagnosticsRunner

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


class TestEnvironmentDependencyChecks(unittest.TestCase):

    def test_host_supported_python_versions_do_not_create_score_penalty(self):
        for version in ((3, 13, 0), (3, 14, 0), (3, 15, 0)):
            with self.subTest(version=version):
                issues = env_deps._check_python_version(
                    {"python_version": version}
                )
                self.assertEqual(issues, [])
                self.assertEqual(HealthReport.compute_health_score(issues), 100)

    def test_python_below_host_minimum_remains_warning(self):
        issues = env_deps._check_python_version(
            {"python_version": (3, 9, 18)}
        )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, IssueSeverity.WARNING)
        self.assertEqual(issues[0].title, "Python Version Too Old")

    def test_torch_below_host_minimum_creates_warning(self):
        issues = env_deps._check_torch_availability({
            "torch_available": True,
            "torch_version": "2.4.1+cu121",
        })

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, IssueSeverity.WARNING)
        self.assertEqual(
            issues[0].title,
            "PyTorch Version Below ComfyUI Minimum",
        )

    def test_torch_minimum_newer_and_unknown_versions_are_safe(self):
        versions = (
            "2.5.0",
            "2.5.0.dev20260719+cu130",
            "2.6.0a0+gitabcdef",
            "2.7.1+cu130",
            "unknown",
            "",
            None,
        )

        for version in versions:
            with self.subTest(version=version):
                issues = env_deps._check_torch_availability({
                    "torch_available": True,
                    "torch_version": version,
                })
                self.assertEqual(issues, [])

    def test_torch_missing_retains_single_critical_issue(self):
        issues = env_deps._check_torch_availability({
            "torch_available": False,
            "torch_version": None,
        })

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, IssueSeverity.CRITICAL)
        self.assertEqual(issues[0].title, "PyTorch Not Available")

    def test_torch_release_prefix_parser_handles_suffixes_and_uncertainty(self):
        cases = {
            "2.4.1+cu121": (2, 4, 1),
            "2.5.0.dev20260719+cu130": (2, 5, 0),
            "2.6.0a0+gitabcdef": (2, 6, 0),
            "2.7": (2, 7, 0),
            "unknown": None,
            "": None,
            None: None,
        }

        for version, expected in cases.items():
            with self.subTest(version=version):
                self.assertEqual(
                    env_deps._parse_release_version(version),
                    expected,
                )


class TestModelAssetsChecks(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        model_assets._clear_path_cache()

    def tearDown(self):
        model_assets._clear_path_cache()

    @staticmethod
    def _asset_workflow(value, node_id=90):
        return {
            "nodes": [
                {
                    "id": node_id,
                    "type": "CheckpointLoaderSimple",
                    "title": "Synthetic Loader",
                    "widgets_values": [value],
                }
            ]
        }

    @staticmethod
    def _checkpoint_paths(root):
        return {
            "checkpoints": [root],
            "input": [],
            "input_3d": [],
            "output": [],
        }

    async def test_model_assets_rejects_traversal_before_exists_or_open(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            registered = base / "registered"
            registered.mkdir()
            outside = base / "outside.safetensors"
            outside.write_bytes(b"x")
            workflow = self._asset_workflow("../outside.safetensors")
            request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
            original_exists = Path.exists
            probed_paths = []

            def exists_spy(path):
                probed_paths.append(os.path.normcase(os.path.abspath(os.fspath(path))))
                return original_exists(path)

            with (
                patch(
                    "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                    return_value=self._checkpoint_paths(registered),
                ),
                patch.object(Path, "exists", autospec=True, side_effect=exists_spy),
                patch("builtins.open", mock_open(read_data=b"x")) as open_mock,
            ):
                issues = await model_assets.check_model_assets(workflow, request)

            self.assertEqual(len(issues), 1)
            issue_text = repr(issues[0].to_dict())
            self.assertNotIn("outside.safetensors", issue_text)
            self.assertNotIn(
                os.path.normcase(os.path.abspath(os.fspath(outside))),
                probed_paths,
            )
            open_mock.assert_not_called()

    async def test_model_assets_rejects_absolute_external_before_exists_or_open(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            registered = base / "registered"
            registered.mkdir()
            outside = base / "absolute-external.safetensors"
            outside.write_bytes(b"x")
            workflow = self._asset_workflow(str(outside))
            request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
            original_exists = Path.exists
            probed_paths = []

            def exists_spy(path):
                probed_paths.append(os.path.normcase(os.path.abspath(os.fspath(path))))
                return original_exists(path)

            with (
                patch(
                    "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                    return_value=self._checkpoint_paths(registered),
                ),
                patch.object(Path, "exists", autospec=True, side_effect=exists_spy),
                patch("builtins.open", mock_open(read_data=b"x")) as open_mock,
            ):
                issues = await model_assets.check_model_assets(workflow, request)

            self.assertEqual(len(issues), 1)
            issue_text = repr(issues[0].to_dict())
            self.assertNotIn("absolute-external.safetensors", issue_text)
            self.assertNotIn(
                os.path.normcase(os.path.abspath(os.fspath(outside))),
                probed_paths,
            )
            open_mock.assert_not_called()

    async def test_model_assets_rejects_embedded_null_without_probe(self):
        with tempfile.TemporaryDirectory() as temp_root:
            registered = Path(temp_root) / "registered"
            registered.mkdir()
            value = "synthetic\x00escape.safetensors"
            workflow = self._asset_workflow(value)
            request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)

            with (
                patch(
                    "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                    return_value=self._checkpoint_paths(registered),
                ),
                patch.object(Path, "exists", autospec=True) as exists_mock,
                patch("builtins.open", mock_open()) as open_mock,
            ):
                issues = await model_assets.check_model_assets(workflow, request)

            self.assertEqual(len(issues), 1)
            self.assertNotIn("escape.safetensors", repr(issues[0].to_dict()))
            exists_mock.assert_not_called()
            open_mock.assert_not_called()

    async def test_model_assets_commonpath_value_error_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_root:
            registered = Path(temp_root) / "registered"
            registered.mkdir()
            (registered / "synthetic.safetensors").write_bytes(b"x")
            workflow = self._asset_workflow("synthetic.safetensors")
            request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)

            with (
                patch(
                    "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                    return_value=self._checkpoint_paths(registered),
                ),
                patch(
                    "services.diagnostics.checks.model_assets.os.path.commonpath",
                    side_effect=ValueError("synthetic cross-drive mismatch"),
                ) as commonpath_mock,
                patch("builtins.open", mock_open()) as open_mock,
            ):
                issues = await model_assets.check_model_assets(workflow, request)

            self.assertEqual(len(issues), 1)
            commonpath_mock.assert_called()
            open_mock.assert_not_called()

    async def test_model_assets_rejects_symlink_escape_before_open(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            registered = base / "registered"
            registered.mkdir()
            outside = base / "symlink-target.safetensors"
            outside.write_bytes(b"x")
            linked = registered / "linked.safetensors"
            try:
                linked.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {type(exc).__name__}")

            workflow = self._asset_workflow(linked.name)
            request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
            with (
                patch(
                    "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                    return_value=self._checkpoint_paths(registered),
                ),
                patch("builtins.open", mock_open(read_data=b"x")) as open_mock,
            ):
                issues = await model_assets.check_model_assets(workflow, request)

            self.assertEqual(len(issues), 1)
            open_mock.assert_not_called()

    async def test_model_assets_rejects_simulated_symlink_realpath_escape(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            registered = base / "registered"
            registered.mkdir()
            linked = registered / "simulated-link.safetensors"
            linked.write_bytes(b"x")
            outside = base / "simulated-target.safetensors"
            outside.write_bytes(b"x")
            workflow = self._asset_workflow(linked.name)
            request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
            original_realpath = os.path.realpath

            def realpath_spy(path):
                normalized = os.path.normcase(os.path.abspath(os.fspath(path)))
                if normalized == os.path.normcase(os.path.abspath(os.fspath(linked))):
                    return os.fspath(outside)
                return original_realpath(path)

            with (
                patch(
                    "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                    return_value=self._checkpoint_paths(registered),
                ),
                patch(
                    "services.diagnostics.checks.model_assets.os.path.realpath",
                    side_effect=realpath_spy,
                ) as realpath_mock,
                patch("builtins.open", mock_open(read_data=b"x")) as open_mock,
            ):
                issues = await model_assets.check_model_assets(workflow, request)

            self.assertEqual(len(issues), 1)
            realpath_mock.assert_called()
            open_mock.assert_not_called()

    async def test_model_assets_rejects_parent_component_even_when_result_is_in_root(self):
        with tempfile.TemporaryDirectory() as temp_root:
            registered = Path(temp_root) / "registered"
            nested = registered / "nested"
            nested.mkdir(parents=True)
            asset = registered / "inside.safetensors"
            asset.write_bytes(b"x")
            workflow = self._asset_workflow("nested/../inside.safetensors")
            request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)

            with (
                patch(
                    "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                    return_value=self._checkpoint_paths(registered),
                ),
                patch("builtins.open", mock_open(read_data=b"x")) as open_mock,
            ):
                issues = await model_assets.check_model_assets(workflow, request)

            self.assertEqual(len(issues), 1)
            self.assertNotIn("inside.safetensors", repr(issues[0].to_dict()))
            open_mock.assert_not_called()

    async def test_model_assets_preserves_nested_and_contained_absolute_paths(self):
        with tempfile.TemporaryDirectory() as temp_root:
            registered = Path(temp_root) / "registered"
            nested = registered / "nested" / "unicode"
            nested.mkdir(parents=True)
            asset = nested / "模型.safetensors"
            asset.write_bytes(b"x")

            with patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value=self._checkpoint_paths(registered),
            ):
                for index, value in enumerate(
                    ("nested/unicode/模型.safetensors", str(asset)),
                    start=91,
                ):
                    with self.subTest(value_kind="absolute" if Path(value).is_absolute() else "relative"):
                        workflow = self._asset_workflow(value, node_id=index)
                        request = HealthCheckRequest(
                            workflow=workflow,
                            scope=DiagnosticsScope.MANUAL,
                        )
                        issues = await model_assets.check_model_assets(workflow, request)

                    self.assertEqual(issues, [])

    async def test_health_check_route_flow_does_not_probe_or_disclose_external_path(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            registered = base / "registered"
            registered.mkdir()
            outside = base / "route-external.safetensors"
            outside.write_bytes(b"x")
            payload = {
                "workflow": self._asset_workflow("../route-external.safetensors"),
                "scope": "manual",
                "options": {"include_intent": False, "max_paths": 50},
            }
            check_request = HealthCheckRequest.from_dict(payload)
            runner = DiagnosticsRunner()
            runner.register_check("model_assets", model_assets.check_model_assets)

            with (
                patch(
                    "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                    return_value=self._checkpoint_paths(registered),
                ),
                patch("builtins.open", mock_open(read_data=b"x")) as open_mock,
            ):
                report = await runner.run(check_request)

            response = {"success": True, "report": report.to_dict()}
            serialized = repr(response)
            self.assertTrue(response["success"])
            self.assertEqual(response["report"]["scope"], "manual")
            self.assertEqual(len(response["report"]["issues"]), 1)
            self.assertNotIn(str(base), serialized)
            self.assertNotIn("../", serialized)
            self.assertNotIn("route-external.safetensors", serialized)
            open_mock.assert_not_called()

    def test_model_assets_discovers_current_host_folders(self):
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            current_categories = {
                "diffusers",
                "gligen",
                "diffusion_models",
                "text_encoders",
                "clip_vision",
                "style_models",
                "photomaker",
                "model_patches",
                "audio_encoders",
                "background_removal",
                "frame_interpolation",
                "geometry_estimation",
                "optical_flow",
                "detection",
            }

            def get_folder_paths(folder_name):
                if folder_name in current_categories:
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
            self.assertEqual(paths["diffusion_models"], [root / "diffusion_models"])
            self.assertEqual(paths["text_encoders"], [root / "text_encoders"])
            self.assertEqual(paths["clip_vision"], [root / "clip_vision"])
            self.assertEqual(paths["style_models"], [root / "style_models"])
            self.assertEqual(paths["photomaker"], [root / "photomaker"])
            self.assertEqual(paths["model_patches"], [root / "model_patches"])
            self.assertEqual(paths["audio_encoders"], [root / "audio_encoders"])
            self.assertEqual(paths["background_removal"], [root / "background_removal"])
            self.assertEqual(paths["frame_interpolation"], [root / "frame_interpolation"])
            self.assertEqual(paths["optical_flow"], [root / "optical_flow"])
            self.assertEqual(paths["diffusers"], [root / "diffusers"])
            self.assertEqual(paths["gligen"], [root / "gligen"])
            self.assertEqual(paths["input_3d"], [root / "input" / "3d"])

    async def test_model_assets_current_loader_references_search_matching_host_folders(self):
        cases = [
            ("DiffusersLoader", "stable-diffusion-v1-5", "diffusers", "dir"),
            ("GLIGENLoader", "gligen_textbox_model.safetensors", "gligen", "file"),
            ("UNETLoader", "wan2_2_high_noise.safetensors", "diffusion_models"),
            ("CLIPLoader", "t5xxl_fp16.safetensors", "text_encoders"),
            ("DualCLIPLoader", "clip_l.safetensors", "text_encoders"),
            ("TripleCLIPLoader", "clip_g.safetensors", "text_encoders"),
            ("QuadrupleCLIPLoader", "llama_8b_3.1_instruct.safetensors", "text_encoders"),
            ("CLIPVisionLoader", "clip_vision_h.safetensors", "clip_vision"),
            ("StyleModelLoader", "style_model.safetensors", "style_models"),
            ("PhotoMakerLoader", "photomaker-v1.bin", "photomaker"),
            ("LoadBackgroundRemovalModel", "birefnet.safetensors", "background_removal"),
            ("FrameInterpolationModelLoader", "film_net_fp32.safetensors", "frame_interpolation"),
            ("OpticalFlowLoader", "raft_large.pth", "optical_flow"),
            ("AudioEncoderLoader", "whisper_audio_encoder.safetensors", "audio_encoders"),
            ("ModelPatchLoader", "wan_multitalk_patch.safetensors", "model_patches"),
            ("Load3D", "3d/character.glb", "input_3d", "file"),
            ("Load3DAdvanced", "3d/scene.stl", "input_3d", "file"),
        ]

        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            paths = {
                "checkpoints": [],
                "vae": [],
                "loras": [],
                "controlnet": [],
                "text_encoders": [],
                "clip_vision": [],
                "style_models": [],
                "diffusion_models": [],
                "photomaker": [],
                "model_patches": [],
                "audio_encoders": [],
                "background_removal": [],
                "frame_interpolation": [],
                "diffusers": [],
                "gligen": [],
                "geometry_estimation": [],
                "optical_flow": [],
                "detection": [],
                "input": [],
                "input_3d": [],
                "output": [],
            }

            for case in cases:
                _node_type, filename, category, *kind = case
                category_dir = root / "models" / category
                category_dir.mkdir(parents=True, exist_ok=True)
                if category == "input_3d" and filename.startswith("3d/"):
                    filename_path = category_dir / filename.removeprefix("3d/")
                else:
                    filename_path = category_dir / filename
                if kind and kind[0] == "dir":
                    filename_path.mkdir(parents=True, exist_ok=True)
                    (filename_path / "model_index.json").write_bytes(b"{}")
                else:
                    filename_path.parent.mkdir(parents=True, exist_ok=True)
                    filename_path.write_bytes(b"x")
                paths[category] = [category_dir]

            with patch("services.diagnostics.checks.model_assets._get_comfy_model_paths", return_value=paths):
                for index, case in enumerate(cases, start=100):
                    node_type, filename, _category, *_kind = case
                    with self.subTest(node_type=node_type):
                        workflow = {"nodes": [{"id": index, "type": node_type, "widgets_values": [filename]}]}
                        request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
                        issues = await model_assets.check_model_assets(workflow, request)

                    self.assertEqual(issues, [])

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

    async def test_model_assets_old_host_does_not_fallback_current_loader_to_checkpoints(self):
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            checkpoint_dir = root / "private" / "models" / "checkpoints"
            checkpoint_dir.mkdir(parents=True)
            (checkpoint_dir / "raft_large.pth").write_bytes(b"x")

            with patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value={
                    "checkpoints": [checkpoint_dir],
                    "optical_flow": [],
                    "input": [],
                    "output": [],
                },
            ):
                workflow = {"nodes": [{"id": 13, "type": "OpticalFlowLoader", "widgets_values": ["raft_large.pth"]}]}
                request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
                issues = await model_assets.check_model_assets(workflow, request)

            self.assertEqual(len(issues), 1)
            self.assertIn("Searched in: optical_flow folders", issues[0].evidence)
            evidence_text = "\n".join([issues[0].summary, *issues[0].evidence])
            self.assertIn("raft_large.pth", evidence_text)
            self.assertNotIn(temp_root, evidence_text)
            self.assertNotIn("private", evidence_text)

    async def test_model_assets_old_host_does_not_fallback_new_loaders_to_checkpoints(self):
        cases = [
            ("DiffusersLoader", "stable-diffusion-v1-5", "diffusers"),
            ("GLIGENLoader", "gligen_textbox_model.safetensors", "gligen"),
            ("Load3D", "3d/character.glb", "input_3d"),
        ]

        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            checkpoint_dir = root / "private" / "models" / "checkpoints"
            checkpoint_dir.mkdir(parents=True)
            (checkpoint_dir / "stable-diffusion-v1-5").mkdir()
            (checkpoint_dir / "gligen_textbox_model.safetensors").write_bytes(b"x")
            (checkpoint_dir / "character.glb").write_bytes(b"x")

            with patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value={
                    "checkpoints": [checkpoint_dir],
                    "diffusers": [],
                    "gligen": [],
                    "input_3d": [],
                    "input": [],
                    "output": [],
                },
            ):
                for index, (node_type, filename, category) in enumerate(cases, start=20):
                    with self.subTest(node_type=node_type):
                        workflow = {"nodes": [{"id": index, "type": node_type, "widgets_values": [filename]}]}
                        request = HealthCheckRequest(workflow=workflow, scope=DiagnosticsScope.MANUAL)
                        issues = await model_assets.check_model_assets(workflow, request)

                    self.assertEqual(len(issues), 1)
                    self.assertIn(f"Searched in: {category} folders", issues[0].evidence)
                    evidence_text = "\n".join([issues[0].summary, *issues[0].evidence])
                    self.assertIn(Path(filename).name, evidence_text)
                    self.assertNotIn(temp_root, evidence_text)
                    self.assertNotIn("private", evidence_text)

    def test_model_assets_preserves_existing_category_detection(self):
        cases = [
            ("CheckpointLoaderSimple", "dreamshaper.safetensors", "checkpoints"),
            ("VAELoader", "anime_vae.safetensors", "vae"),
            ("LoraLoader", "detail_lora.safetensors", "loras"),
            ("ControlNetLoader", "pose_controlnet.safetensors", "controlnet"),
            ("CLIPLoader", "clip_l.safetensors", "text_encoders"),
            ("DualCLIPLoader", "clip_l.safetensors", "text_encoders"),
            ("TripleCLIPLoader", "clip_g.safetensors", "text_encoders"),
            ("QuadrupleCLIPLoader", "llama_8b_3.1_instruct.safetensors", "text_encoders"),
            ("UNETLoader", "flux1-dev.safetensors", "diffusion_models"),
            ("DiffusersLoader", "stable-diffusion-v1-5", "diffusers"),
            ("CLIPVisionLoader", "clip_vision_h.safetensors", "clip_vision"),
            ("StyleModelLoader", "style_model.safetensors", "style_models"),
            ("GLIGENLoader", "gligen_textbox_model.safetensors", "gligen"),
            ("PhotoMakerLoader", "photomaker-v1.bin", "photomaker"),
            ("LoadBackgroundRemovalModel", "birefnet.safetensors", "background_removal"),
            ("FrameInterpolationModelLoader", "film_net_fp32.safetensors", "frame_interpolation"),
            ("OpticalFlowLoader", "raft_large.pth", "optical_flow"),
            ("AudioEncoderLoader", "whisper_audio_encoder.safetensors", "audio_encoders"),
            ("ModelPatchLoader", "wan_multitalk_patch.safetensors", "model_patches"),
            ("UpscaleModelLoader", "realesrgan.safetensors", "upscale_models"),
            ("EmbeddingLoader", "bad-hands.pt", "embeddings"),
            ("LoadImage", "example.png", "input"),
            ("Load3D", "3d/character.glb", "input_3d"),
            ("Load3DAdvanced", "3d/scene.stl", "input_3d"),
        ]

        for node_type, filename, expected in cases:
            with self.subTest(node_type=node_type):
                self.assertEqual(model_assets._determine_asset_category(node_type, filename), expected)

    def test_model_assets_recognizes_current_host_3d_extensions(self):
        for extension in [".gltf", ".glb", ".obj", ".fbx", ".stl", ".spz", ".splat", ".ply", ".ksplat"]:
            with self.subTest(extension=extension):
                self.assertTrue(model_assets._is_path_like(f"3d/example{extension}"))

if __name__ == '__main__':
    unittest.main(verbosity=2)

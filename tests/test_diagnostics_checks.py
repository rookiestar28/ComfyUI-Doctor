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
        versions = (
            "2.4.1+cu121",
            "2.5.0",
            "2.5.0.dev20260719+cu130",
            "2.6.0a0+gitabcdef",
            "v2.6.1+cu130",
        )

        for version in versions:
            with self.subTest(version=version):
                issues = env_deps._check_torch_availability({
                    "torch_available": True,
                    "torch_version": version,
                })

                self.assertEqual(len(issues), 1)
                self.assertEqual(issues[0].category, IssueCategory.DEPS)
                self.assertEqual(issues[0].severity, IssueSeverity.WARNING)
                self.assertEqual(
                    issues[0].title,
                    "PyTorch Version Below ComfyUI Minimum",
                )
                self.assertEqual(issues[0].target.setting, "torch")
                self.assertIn(
                    "minimum supported version 2.7",
                    issues[0].summary,
                )
                self.assertIn(
                    "ComfyUI minimum supported release: 2.7",
                    issues[0].evidence,
                )
                self.assertIn(
                    "Upgrade to PyTorch 2.7 or newer",
                    issues[0].recommendation,
                )

    def test_torch_minimum_newer_and_unknown_versions_are_safe(self):
        versions = (
            "2.7",
            "2.7.0.dev20260719+cu130",
            "2.7.1+cu130",
            "2.8.0a0+gitabcdef",
            "3.0.0",
            "unknown",
            "",
            None,
            2.7,
        )

        for version in versions:
            with self.subTest(version=version):
                issues = env_deps._check_torch_availability({
                    "torch_available": True,
                    "torch_version": version,
                })
                self.assertEqual(issues, [])

    def test_public_guidance_uses_host_pytorch_27_minimum(self):
        root = Path(__file__).resolve().parent.parent
        readme = (root / "README.md").read_text(encoding="utf-8")
        user_guide = (root / "docs" / "USER_GUIDE.md").read_text(encoding="utf-8")

        self.assertIn("PyTorch versions below 2.7", readme)
        self.assertNotIn("PyTorch versions below 2.5", readme)
        self.assertIn("PyTorch-below-2.7 guidance", user_guide)
        self.assertNotIn("PyTorch-below-2.5 guidance", user_guide)

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

    @staticmethod
    def _sam3d_workflow(value, *, node_id=1550, named=False):
        node = {
            "id": node_id,
            "type": "SAM3DBody_Loader",
            "title": "Synthetic SAM3D Body Loader",
            "inputs": [
                {
                    "name": "model_file",
                    "widget": {"name": "model_file"},
                }
            ],
        }
        if named:
            node["widgets_values_named"] = {"model_file": value}
        else:
            node["widgets_values"] = [value]
        return {"nodes": [node]}

    @staticmethod
    def _sam3d_paths(*, checkpoints=(), detection=()):
        return {
            "checkpoints": list(checkpoints),
            "detection": list(detection),
            "input": [],
            "input_3d": [],
            "output": [],
        }

    @staticmethod
    def _dataset_paths(input_root, dataset_roots=()):
        return {
            "checkpoints": [],
            "input": [input_root],
            "input_3d": [],
            "output": [],
            "datasets": list(dataset_roots),
        }

    @staticmethod
    def _dataset_workflow(
        node_type,
        widget_name,
        value,
        *,
        node_id=1500,
        named=False,
    ):
        node = {
            "id": node_id,
            "type": node_type,
            "title": "Synthetic Dataset Loader",
            "inputs": [
                {
                    "name": widget_name,
                    "widget": {"name": widget_name},
                }
            ],
        }
        if named:
            node["widgets_values_named"] = {widget_name: value}
        else:
            node["widgets_values"] = [value]
        return {"nodes": [node]}

    async def test_dataset_input_loaders_report_only_missing_contained_folders(self):
        loader_types = (
            "LoadImageDataSetFromFolder",
            "LoadImageTextDataSetFromFolder",
            "LoadVideoDataSetFromFolder",
            "LoadVideoTextDataSetFromFolder",
        )
        with tempfile.TemporaryDirectory() as temp_root:
            input_root = Path(temp_root) / "input"
            input_root.mkdir()
            (input_root / "existing_dataset").mkdir()
            paths = self._dataset_paths(input_root)

            for index, node_type in enumerate(loader_types):
                with self.subTest(node_type=node_type, state="existing"):
                    workflow = self._dataset_workflow(
                        node_type,
                        "folder",
                        "existing_dataset",
                        node_id=1500 + index,
                    )
                    with patch(
                        "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                        return_value=paths,
                    ):
                        issues = await model_assets.check_model_assets(
                            workflow,
                            HealthCheckRequest(
                                workflow=workflow,
                                scope=DiagnosticsScope.MANUAL,
                            ),
                        )
                    self.assertEqual(issues, [])

                with self.subTest(node_type=node_type, state="missing"):
                    workflow = self._dataset_workflow(
                        node_type,
                        "folder",
                        f"missing_dataset_{index}",
                        node_id=1510 + index,
                    )
                    with patch(
                        "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                        return_value=paths,
                    ):
                        issues = await model_assets.check_model_assets(
                            workflow,
                            HealthCheckRequest(
                                workflow=workflow,
                                scope=DiagnosticsScope.MANUAL,
                            ),
                        )

                    self.assertEqual(len(issues), 1)
                    serialized = repr(issues[0].to_dict())
                    self.assertIn(f"missing_dataset_{index}", serialized)
                    self.assertIn("input", serialized)
                    self.assertNotIn(temp_root, serialized)

    async def test_training_dataset_named_value_uses_only_registered_dataset_roots(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            input_root = base / "input"
            dataset_root = base / "datasets"
            input_root.mkdir()
            dataset_root.mkdir()
            (dataset_root / "existing_training").mkdir()
            (input_root / "wrong_root_only").mkdir()
            paths = self._dataset_paths(input_root, [dataset_root])

            existing_workflow = self._dataset_workflow(
                "LoadTrainingDataset",
                "folder_name",
                "existing_training",
                named=True,
            )
            wrong_root_workflow = self._dataset_workflow(
                "LoadTrainingDataset",
                "folder_name",
                "wrong_root_only",
                node_id=1521,
                named=True,
            )

            with patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value=paths,
            ):
                existing_issues = await model_assets.check_model_assets(
                    existing_workflow,
                    HealthCheckRequest(
                        workflow=existing_workflow,
                        scope=DiagnosticsScope.MANUAL,
                    ),
                )
                wrong_root_issues = await model_assets.check_model_assets(
                    wrong_root_workflow,
                    HealthCheckRequest(
                        workflow=wrong_root_workflow,
                        scope=DiagnosticsScope.MANUAL,
                    ),
                )

        self.assertEqual(existing_issues, [])
        self.assertEqual(len(wrong_root_issues), 1)
        serialized = repr(wrong_root_issues[0].to_dict())
        self.assertIn("wrong_root_only", serialized)
        self.assertIn("datasets", serialized)
        self.assertNotIn(temp_root, serialized)

    async def test_training_dataset_uses_empty_extension_host_registry_category(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            dataset_root = base / "datasets"
            dataset_root.mkdir()
            folder_paths = SimpleNamespace(
                folder_names_and_paths={
                    "datasets": ([str(dataset_root)], set()),
                },
                get_input_directory=lambda: str(base / "input"),
                get_output_directory=lambda: str(base / "output"),
            )
            workflow = self._dataset_workflow(
                "LoadTrainingDataset",
                "folder_name",
                "missing_registered_training",
            )

            with patch.dict(sys.modules, {"folder_paths": folder_paths}):
                issues = await model_assets.check_model_assets(
                    workflow,
                    HealthCheckRequest(
                        workflow=workflow,
                        scope=DiagnosticsScope.MANUAL,
                    ),
                )

        self.assertEqual(len(issues), 1)
        serialized = repr(issues[0].to_dict())
        self.assertIn("missing_registered_training", serialized)
        self.assertIn("datasets", serialized)
        self.assertNotIn(temp_root, serialized)

    async def test_input_dataset_loader_does_not_fall_back_to_dataset_root(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            input_root = base / "input"
            dataset_root = base / "datasets"
            input_root.mkdir()
            dataset_root.mkdir()
            (dataset_root / "wrong_root_only").mkdir()
            paths = self._dataset_paths(input_root, [dataset_root])
            workflow = self._dataset_workflow(
                "LoadImageDataSetFromFolder",
                "folder",
                "wrong_root_only",
                named=True,
            )

            with patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value=paths,
            ):
                issues = await model_assets.check_model_assets(
                    workflow,
                    HealthCheckRequest(
                        workflow=workflow,
                        scope=DiagnosticsScope.MANUAL,
                    ),
                )

        self.assertEqual(len(issues), 1)
        self.assertIn("input", repr(issues[0].to_dict()))

    async def test_dataset_mapping_ignores_unrelated_folder_widgets_and_old_registry(self):
        with tempfile.TemporaryDirectory() as temp_root:
            input_root = Path(temp_root) / "input"
            input_root.mkdir()
            paths = self._dataset_paths(input_root)
            unrelated = self._dataset_workflow(
                "CustomFolderLoader",
                "folder",
                "missing_custom_folder",
            )
            old_host = self._dataset_workflow(
                "LoadTrainingDataset",
                "folder_name",
                "missing_training",
                node_id=1531,
            )
            wrong_widget = self._dataset_workflow(
                "LoadImageDataSetFromFolder",
                "unrelated_folder",
                "missing_wrong_widget",
                node_id=1532,
            )

            with patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value=paths,
            ):
                unrelated_issues = await model_assets.check_model_assets(
                    unrelated,
                    HealthCheckRequest(
                        workflow=unrelated,
                        scope=DiagnosticsScope.MANUAL,
                    ),
                )
                old_host_issues = await model_assets.check_model_assets(
                    old_host,
                    HealthCheckRequest(
                        workflow=old_host,
                        scope=DiagnosticsScope.MANUAL,
                    ),
                )
                wrong_widget_issues = await model_assets.check_model_assets(
                    wrong_widget,
                    HealthCheckRequest(
                        workflow=wrong_widget,
                        scope=DiagnosticsScope.MANUAL,
                    ),
                )

        self.assertEqual(unrelated_issues, [])
        self.assertEqual(old_host_issues, [])
        self.assertEqual(wrong_widget_issues, [])

    async def test_dataset_rejects_external_candidates_before_directory_probes(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            input_root = base / "input"
            input_root.mkdir()
            outside = base / "outside_dataset"
            outside.mkdir()
            paths = self._dataset_paths(input_root)
            candidates = (
                "../outside_dataset",
                str(outside),
                "nul\x00dataset",
                "x" * (model_assets.MAX_NAMED_WIDGET_VALUE_LENGTH + 1),
            )

            for index, candidate in enumerate(candidates):
                with self.subTest(index=index):
                    workflow = self._dataset_workflow(
                        "LoadImageDataSetFromFolder",
                        "folder",
                        candidate,
                        node_id=1540 + index,
                    )
                    with (
                        patch(
                            "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                            return_value=paths,
                        ),
                        patch.object(
                            Path,
                            "is_dir",
                            side_effect=AssertionError(
                                "directory probe must follow containment"
                            ),
                        ) as is_dir_mock,
                        patch.object(
                            Path,
                            "iterdir",
                            side_effect=AssertionError(
                                "dataset lookup must not enumerate directories"
                            ),
                        ) as iterdir_mock,
                        patch(
                            "services.diagnostics.checks.model_assets.os.access",
                            side_effect=AssertionError(
                                "readability probe must follow containment"
                            ),
                        ) as access_mock,
                        patch("os.listdir") as listdir_mock,
                        patch("builtins.open", mock_open()) as open_mock,
                    ):
                        issues = await model_assets.check_model_assets(
                            workflow,
                            HealthCheckRequest(
                                workflow=workflow,
                                scope=DiagnosticsScope.MANUAL,
                            ),
                        )

                    self.assertEqual(len(issues), 1)
                    serialized = repr(issues[0].to_dict())
                    self.assertIn(
                        model_assets.INVALID_ASSET_DISPLAY_NAME,
                        serialized,
                    )
                    self.assertNotIn("outside_dataset", serialized)
                    self.assertNotIn(temp_root, serialized)
                    self.assertLess(len(serialized), 2000)
                    is_dir_mock.assert_not_called()
                    iterdir_mock.assert_not_called()
                    access_mock.assert_not_called()
                    listdir_mock.assert_not_called()
                    open_mock.assert_not_called()

    async def test_dataset_rejects_symlink_escape_before_directory_probes(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            input_root = base / "input"
            input_root.mkdir()
            outside = base / "outside_dataset"
            outside.mkdir()
            linked = input_root / "linked_dataset"
            try:
                linked.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(
                    f"symlink creation unavailable: {type(exc).__name__}"
                )

            workflow = self._dataset_workflow(
                "LoadVideoDataSetFromFolder",
                "folder",
                linked.name,
            )
            with (
                patch(
                    "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                    return_value=self._dataset_paths(input_root),
                ),
                patch.object(Path, "is_dir") as is_dir_mock,
                patch(
                    "services.diagnostics.checks.model_assets.os.access"
                ) as access_mock,
                patch("os.listdir") as listdir_mock,
                patch("builtins.open", mock_open()) as open_mock,
            ):
                issues = await model_assets.check_model_assets(
                    workflow,
                    HealthCheckRequest(
                        workflow=workflow,
                        scope=DiagnosticsScope.MANUAL,
                    ),
                )

            self.assertEqual(len(issues), 1)
            self.assertIn(
                model_assets.INVALID_ASSET_DISPLAY_NAME,
                repr(issues[0].to_dict()),
            )
            is_dir_mock.assert_not_called()
            access_mock.assert_not_called()
            listdir_mock.assert_not_called()
            open_mock.assert_not_called()

    async def test_dataset_rejects_simulated_symlink_escape_before_probes(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            input_root = base / "input"
            input_root.mkdir()
            linked = input_root / "simulated_link"
            linked.mkdir()
            outside = base / "simulated_outside"
            outside.mkdir()
            original_realpath = os.path.realpath

            def realpath_spy(path):
                normalized = os.path.normcase(
                    os.path.abspath(os.fspath(path))
                )
                if normalized == os.path.normcase(
                    os.path.abspath(os.fspath(linked))
                ):
                    return os.fspath(outside)
                return original_realpath(path)

            workflow = self._dataset_workflow(
                "LoadVideoTextDataSetFromFolder",
                "folder",
                linked.name,
            )
            with (
                patch(
                    "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                    return_value=self._dataset_paths(input_root),
                ),
                patch(
                    "services.diagnostics.checks.model_assets.os.path.realpath",
                    side_effect=realpath_spy,
                ) as realpath_mock,
                patch.object(Path, "is_dir") as is_dir_mock,
                patch(
                    "services.diagnostics.checks.model_assets.os.access"
                ) as access_mock,
                patch("os.listdir") as listdir_mock,
                patch("builtins.open", mock_open()) as open_mock,
            ):
                issues = await model_assets.check_model_assets(
                    workflow,
                    HealthCheckRequest(
                        workflow=workflow,
                        scope=DiagnosticsScope.MANUAL,
                    ),
                )

            self.assertEqual(len(issues), 1)
            self.assertIn(
                model_assets.INVALID_ASSET_DISPLAY_NAME,
                repr(issues[0].to_dict()),
            )
            realpath_mock.assert_called()
            is_dir_mock.assert_not_called()
            access_mock.assert_not_called()
            listdir_mock.assert_not_called()
            open_mock.assert_not_called()

    async def test_dataset_unreadable_folder_is_reported_without_enumeration(self):
        with tempfile.TemporaryDirectory() as temp_root:
            input_root = Path(temp_root) / "input"
            input_root.mkdir()
            (input_root / "unreadable_dataset").mkdir()
            workflow = self._dataset_workflow(
                "LoadImageTextDataSetFromFolder",
                "folder",
                "unreadable_dataset",
            )

            with (
                patch(
                    "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                    return_value=self._dataset_paths(input_root),
                ),
                patch(
                    "services.diagnostics.checks.model_assets.os.access",
                    return_value=False,
                ) as access_mock,
                patch.object(Path, "iterdir") as iterdir_mock,
                patch("os.listdir") as listdir_mock,
                patch("builtins.open", mock_open()) as open_mock,
            ):
                issues = await model_assets.check_model_assets(
                    workflow,
                    HealthCheckRequest(
                        workflow=workflow,
                        scope=DiagnosticsScope.MANUAL,
                    ),
                )

            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].title, "Dataset Folder Not Readable")
            self.assertNotIn(temp_root, repr(issues[0].to_dict()))
            access_mock.assert_called_once()
            iterdir_mock.assert_not_called()
            listdir_mock.assert_not_called()
            open_mock.assert_not_called()

    async def test_dataset_values_obey_path_budget(self):
        with tempfile.TemporaryDirectory() as temp_root:
            input_root = Path(temp_root) / "input"
            input_root.mkdir()
            workflow = {
                "nodes": [
                    self._dataset_workflow(
                        "LoadImageDataSetFromFolder",
                        "folder",
                        f"missing_dataset_{index}",
                        node_id=1560 + index,
                        named=index % 2 == 1,
                    )["nodes"][0]
                    for index in range(3)
                ]
            }

            with patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value=self._dataset_paths(input_root),
            ):
                issues = await model_assets.check_model_assets(
                    workflow,
                    HealthCheckRequest(
                        workflow=workflow,
                        scope=DiagnosticsScope.MANUAL,
                        max_paths=1,
                    ),
                )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].target.node_id, 1560)

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

    def test_model_assets_sam3d_body_uses_exact_detection_contract(self):
        self.assertIn(
            "SAM3DBody_Loader",
            model_assets.EXACT_FILE_LOADING_NODE_TYPES,
        )
        self.assertEqual(
            model_assets._determine_asset_category(
                "SAM3DBody_Loader",
                "sam3d_body.safetensors",
            ),
            "detection",
        )

        for unrelated_type in (
            "CustomSAM3DBody_Loader",
            "SAMBodyLoader",
            "UnrelatedModelLoader",
        ):
            with self.subTest(unrelated_type=unrelated_type):
                self.assertEqual(
                    model_assets._determine_asset_category(
                        unrelated_type,
                        "shared.safetensors",
                    ),
                    "checkpoints",
                )

    async def test_model_assets_sam3d_body_resolves_registered_detection_asset(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            checkpoint_root = base / "checkpoints"
            detection_root = base / "detection"
            checkpoint_root.mkdir()
            detection_root.mkdir()
            (detection_root / "sam3d_body.safetensors").write_bytes(b"x")
            paths = self._sam3d_paths(
                checkpoints=[checkpoint_root],
                detection=[detection_root],
            )

            for named in (False, True):
                with self.subTest(named=named), patch(
                    "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                    return_value=paths,
                ):
                    workflow = self._sam3d_workflow(
                        "sam3d_body.safetensors",
                        named=named,
                    )
                    issues = await model_assets.check_model_assets(
                        workflow,
                        HealthCheckRequest(
                            workflow=workflow,
                            scope=DiagnosticsScope.MANUAL,
                        ),
                    )

                self.assertEqual(issues, [])

    async def test_model_assets_sam3d_body_missing_uses_sanitized_detection_issue(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            checkpoint_root = base / "private" / "checkpoints"
            detection_root = base / "private" / "detection"
            checkpoint_root.mkdir(parents=True)
            detection_root.mkdir(parents=True)
            workflow = self._sam3d_workflow("missing_sam3d_body.safetensors")
            paths = self._sam3d_paths(
                checkpoints=[checkpoint_root],
                detection=[detection_root],
            )

            with patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value=paths,
            ):
                issues = await model_assets.check_model_assets(
                    workflow,
                    HealthCheckRequest(
                        workflow=workflow,
                        scope=DiagnosticsScope.MANUAL,
                    ),
                )

            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].severity.value, "warning")
            self.assertIn("Searched in: detection folders", issues[0].evidence)
            serialized = repr(issues[0].to_dict())
            self.assertIn("missing_sam3d_body.safetensors", serialized)
            self.assertNotIn(temp_root, serialized)
            self.assertNotIn("private", serialized)

    async def test_model_assets_sam3d_body_does_not_fallback_to_checkpoints(self):
        with tempfile.TemporaryDirectory() as temp_root:
            checkpoint_root = Path(temp_root) / "checkpoints"
            checkpoint_root.mkdir()
            (checkpoint_root / "sam3d_body.safetensors").write_bytes(b"x")
            workflow = self._sam3d_workflow("sam3d_body.safetensors")

            for detection_roots in ([], [Path(temp_root) / "missing-detection"]):
                with self.subTest(detection_roots=detection_roots), patch(
                    "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                    return_value=self._sam3d_paths(
                        checkpoints=[checkpoint_root],
                        detection=detection_roots,
                    ),
                ):
                    issues = await model_assets.check_model_assets(
                        workflow,
                        HealthCheckRequest(
                            workflow=workflow,
                            scope=DiagnosticsScope.MANUAL,
                        ),
                    )

                self.assertEqual(len(issues), 1)
                self.assertIn(
                    "Searched in: detection folders",
                    issues[0].evidence,
                )

    async def test_model_assets_sam3d_body_traversal_never_probes_or_discloses(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            checkpoint_root = base / "checkpoints"
            detection_root = base / "detection"
            checkpoint_root.mkdir()
            detection_root.mkdir()
            workflow = self._sam3d_workflow("../external.safetensors")

            with (
                patch(
                    "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                    return_value=self._sam3d_paths(
                        checkpoints=[checkpoint_root],
                        detection=[detection_root],
                    ),
                ),
                patch.object(Path, "exists", autospec=True) as exists_mock,
                patch("builtins.open", mock_open()) as open_mock,
            ):
                issues = await model_assets.check_model_assets(
                    workflow,
                    HealthCheckRequest(
                        workflow=workflow,
                        scope=DiagnosticsScope.MANUAL,
                    ),
                )

            self.assertEqual(len(issues), 1)
            serialized = repr(issues[0].to_dict())
            self.assertNotIn("external.safetensors", serialized)
            self.assertNotIn(temp_root, serialized)
            exists_mock.assert_not_called()
            open_mock.assert_not_called()

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

    def test_model_assets_uses_live_registry_paths_and_extensions_authoritatively(self):
        with tempfile.TemporaryDirectory() as temp_root:
            root = Path(temp_root)
            checkpoint_root = root / "configured" / "checkpoints"
            custom_root = root / "registered" / "doctor_models"
            registry = {
                "checkpoints": (
                    [str(checkpoint_root)],
                    {".safetensors", ".pt2", ".sft"},
                ),
                "doctor_models": ([str(custom_root)], {".doctor"}),
                "malformed": "not-a-registry-entry",
                42: ([str(root / "ignored")], {".bin"}),
            }
            folder_paths = SimpleNamespace(
                folder_names_and_paths=registry,
                get_folder_paths=MagicMock(
                    side_effect=AssertionError(
                        "legacy lookup must not run when the registry exists"
                    )
                ),
                get_input_directory=lambda: str(root / "input"),
                get_output_directory=lambda: str(root / "output"),
            )

            with patch.dict(sys.modules, {"folder_paths": folder_paths}):
                paths = model_assets._get_comfy_model_paths()
                extensions = model_assets._get_comfy_model_extensions()

            self.assertEqual(paths["checkpoints"], [checkpoint_root])
            self.assertEqual(paths["doctor_models"], [custom_root])
            self.assertNotIn("malformed", paths)
            self.assertNotIn(42, paths)
            self.assertEqual(
                extensions["checkpoints"],
                {".safetensors", ".pt2", ".sft"},
            )
            self.assertEqual(extensions["doctor_models"], {".doctor"})
            self.assertFalse(
                model_assets._is_path_like("not_registered.ckpt")
            )
            folder_paths.get_folder_paths.assert_not_called()

    def test_model_assets_recognizes_current_host_model_extensions(self):
        for extension in (".pt2", ".sft"):
            with self.subTest(extension=extension):
                self.assertTrue(
                    model_assets._is_path_like(f"synthetic_model{extension}")
                )

    async def test_model_assets_resolves_custom_registered_category(self):
        with tempfile.TemporaryDirectory() as temp_root:
            custom_root = Path(temp_root) / "configured" / "doctor_models"
            custom_root.mkdir(parents=True)
            (custom_root / "synthetic.doctor").write_bytes(b"x")
            folder_paths = SimpleNamespace(
                folder_names_and_paths={
                    "doctor_models": ([str(custom_root)], {".doctor"}),
                },
                get_input_directory=lambda: str(Path(temp_root) / "input"),
                get_output_directory=lambda: str(Path(temp_root) / "output"),
            )
            workflow = {
                "nodes": [
                    {
                        "id": 130,
                        "type": "DoctorModelLoader",
                        "widgets_values": ["synthetic.doctor"],
                    }
                ]
            }
            request = HealthCheckRequest(
                workflow=workflow,
                scope=DiagnosticsScope.MANUAL,
            )

            with patch.dict(sys.modules, {"folder_paths": folder_paths}):
                issues = await model_assets.check_model_assets(
                    workflow,
                    request,
                )

            self.assertEqual(issues, [])
            self.assertEqual(
                model_assets._determine_asset_category(
                    "DoctorModelLoader",
                    "synthetic.doctor",
                ),
                "doctor_models",
            )

    async def test_dynamic_registry_root_keeps_s21_containment(self):
        with tempfile.TemporaryDirectory() as temp_root:
            base = Path(temp_root)
            custom_root = base / "registered" / "doctor_models"
            custom_root.mkdir(parents=True)
            outside = base / "external.doctor"
            outside.write_bytes(b"x")
            folder_paths = SimpleNamespace(
                folder_names_and_paths={
                    "doctor_models": ([str(custom_root)], {".doctor"}),
                },
                get_input_directory=lambda: str(base / "input"),
                get_output_directory=lambda: str(base / "output"),
            )
            workflow = {
                "nodes": [
                    {
                        "id": 131,
                        "type": "DoctorModelLoader",
                        "title": "Synthetic Custom Loader",
                        "widgets_values": ["../external.doctor"],
                    }
                ]
            }
            request = HealthCheckRequest(
                workflow=workflow,
                scope=DiagnosticsScope.MANUAL,
            )

            with (
                patch.dict(sys.modules, {"folder_paths": folder_paths}),
                patch("builtins.open", mock_open()) as open_mock,
            ):
                issues = await model_assets.check_model_assets(
                    workflow,
                    request,
                )

            self.assertEqual(len(issues), 1)
            serialized = repr(issues[0].to_dict())
            self.assertNotIn("external.doctor", serialized)
            self.assertNotIn(temp_root, serialized)
            open_mock.assert_not_called()

    async def test_named_widget_root_value_is_diagnosed_without_raw_map_evidence(self):
        workflow = {
            "nodes": [
                {
                    "id": 132,
                    "type": "CheckpointLoaderSimple",
                    "inputs": [
                        {
                            "name": "ckpt_name",
                            "widget": {"name": "ckpt_name"},
                        }
                    ],
                    "widgets_values_named": {
                        "ckpt_name": "named_root_missing.safetensors",
                    },
                }
            ]
        }
        request = HealthCheckRequest(
            workflow=workflow,
            scope=DiagnosticsScope.MANUAL,
        )

        with patch(
            "services.diagnostics.checks.model_assets._get_comfy_model_paths",
            return_value=self._checkpoint_paths(Path("synthetic-empty-root")),
        ):
            issues = await model_assets.check_model_assets(workflow, request)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].target.node_id, 132)
        serialized = repr(issues[0].to_dict())
        self.assertIn("named_root_missing.safetensors", serialized)
        self.assertNotIn("widgets_values_named", serialized)
        self.assertNotIn("ckpt_name", serialized)

    async def test_named_widget_dual_and_conflict_keep_positional_precedence(self):
        with tempfile.TemporaryDirectory() as temp_root:
            checkpoint_root = Path(temp_root) / "checkpoints"
            checkpoint_root.mkdir()
            (checkpoint_root / "positional_present.safetensors").write_bytes(
                b"x"
            )
            paths = self._checkpoint_paths(checkpoint_root)
            node_input = {
                "name": "ckpt_name",
                "widget": {"name": "ckpt_name"},
            }
            dual_workflow = {
                "nodes": [
                    {
                        "id": 133,
                        "type": "CheckpointLoaderSimple",
                        "inputs": [node_input],
                        "widgets_values": ["dual_missing.safetensors"],
                        "widgets_values_named": {
                            "ckpt_name": "dual_missing.safetensors",
                        },
                    }
                ]
            }
            conflict_workflow = {
                "nodes": [
                    {
                        "id": 134,
                        "type": "CheckpointLoaderSimple",
                        "inputs": [node_input],
                        "widgets_values": ["positional_present.safetensors"],
                        "widgets_values_named": {
                            "ckpt_name": "named_conflict_missing.safetensors",
                        },
                    }
                ]
            }

            with patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value=paths,
            ):
                dual_issues = await model_assets.check_model_assets(
                    dual_workflow,
                    HealthCheckRequest(
                        workflow=dual_workflow,
                        scope=DiagnosticsScope.MANUAL,
                    ),
                )
                conflict_issues = await model_assets.check_model_assets(
                    conflict_workflow,
                    HealthCheckRequest(
                        workflow=conflict_workflow,
                        scope=DiagnosticsScope.MANUAL,
                    ),
                )

        self.assertEqual(len(dual_issues), 1)
        self.assertIn(
            "dual_missing.safetensors",
            repr(dual_issues[0].to_dict()),
        )
        self.assertEqual(conflict_issues, [])

    async def test_named_widget_malformed_maps_preserve_positional_behavior(self):
        malformed_values = (
            None,
            [],
            {"__proto__": "reserved_missing.safetensors"},
            {"k" * 129: "oversized_key_missing.safetensors"},
            {"ckpt_name": 42},
            {
                f"unknown_{index}": f"ignored_{index}.safetensors"
                for index in range(300)
            },
        )
        empty_paths = self._checkpoint_paths(Path("synthetic-empty-root"))

        for index, named_values in enumerate(malformed_values, start=1):
            with self.subTest(index=index):
                workflow = {
                    "nodes": [
                        {
                            "id": 135 + index,
                            "type": "CheckpointLoaderSimple",
                            "widgets_values": [
                                f"positional_{index}_missing.safetensors"
                            ],
                            "widgets_values_named": named_values,
                        }
                    ]
                }
                with patch(
                    "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                    return_value=empty_paths,
                ):
                    issues = await model_assets.check_model_assets(
                        workflow,
                        HealthCheckRequest(
                            workflow=workflow,
                            scope=DiagnosticsScope.MANUAL,
                        ),
                    )

                self.assertEqual(len(issues), 1)
                serialized = repr(issues[0].to_dict())
                self.assertIn(
                    f"positional_{index}_missing.safetensors",
                    serialized,
                )
                self.assertNotIn("reserved_missing", serialized)
                self.assertNotIn("oversized_key_missing", serialized)

    def test_named_widget_resolution_rejects_ambiguous_and_oversized_shapes(self):
        self.assertEqual(
            model_assets._safe_named_widget_values(
                {
                    "widgets_values_named": {
                        "ckpt_name": "bounded_missing.safetensors",
                    }
                }
            ),
            {"ckpt_name": "bounded_missing.safetensors"},
        )
        self.assertEqual(
            model_assets._safe_named_widget_values(
                {
                    "widgets_values_named": {
                        f"key_{index}": "ignored.safetensors"
                        for index in range(
                            model_assets.MAX_NAMED_WIDGET_ENTRIES + 1
                        )
                    }
                }
            ),
            {},
        )
        self.assertEqual(
            model_assets._effective_widget_values(
                {
                    "inputs": [
                        {
                            "name": "first",
                            "widget": {"name": "ckpt_name"},
                        },
                        {
                            "name": "second",
                            "widget": {"name": "ckpt_name"},
                        },
                    ],
                    "widgets_values_named": {
                        "ckpt_name": "ambiguous_missing.safetensors",
                    },
                }
            ),
            (),
        )
        self.assertEqual(
            model_assets._effective_widget_values(
                {
                    "inputs": [
                        {
                            "name": "malformed",
                            "widget": {"name": ["not", "a", "string"]},
                        },
                        {
                            "name": "ckpt_name",
                            "widget": {"name": "ckpt_name"},
                        },
                    ],
                    "widgets_values": [None],
                    "widgets_values_named": {
                        "ckpt_name": "correct_slot_missing.safetensors",
                    },
                }
            ),
            (None, "correct_slot_missing.safetensors"),
        )
        self.assertEqual(
            model_assets._effective_widget_values(
                {
                    "inputs": [
                        {
                            "name": "ckpt_name",
                            "widget": {"name": "ckpt_name"},
                        }
                    ],
                    "widgets_values": [7],
                    "widgets_values_named": {
                        "ckpt_name": "must_not_override.safetensors",
                    },
                }
            ),
            (7,),
        )
        self.assertEqual(
            model_assets._effective_widget_values(
                {
                    "inputs": [
                        {
                            "name": f"input_{index}",
                            "widget": {"name": f"widget_{index}"},
                        }
                        for index in range(
                            model_assets.MAX_NAMED_WIDGET_ENTRIES + 1
                        )
                    ],
                    "widgets_values_named": {
                        "ckpt_name": "must_not_bypass_schema_limit.safetensors",
                    },
                }
            ),
            (),
        )

    def test_named_widget_malformed_promoted_input_name_fails_open(self):
        definition = self._subgraph_definition(
            "malformed-named-input",
            [
                {
                    "id": 9,
                    "type": "CheckpointLoaderSimple",
                    "inputs": [
                        {
                            "name": "ckpt_name",
                            "widget": {"name": "ckpt_name"},
                        }
                    ],
                    "widgets_values": ["interior_positional.safetensors"],
                }
            ],
            inputs=[
                {
                    "name": ["not", "hashable"],
                    "linkIds": [1],
                }
            ],
            links=[
                {
                    "id": 1,
                    "origin_id": -10,
                    "origin_slot": 0,
                    "target_id": 9,
                    "target_slot": 0,
                }
            ],
        )
        children = model_assets._apply_promoted_widget_values(
            definition,
            {
                "widgets_values_named": {
                    "ckpt_name": "named_must_not_apply.safetensors",
                }
            },
        )

        self.assertEqual(len(children), 1)
        child, promoted_indexes = children[0]
        self.assertEqual(
            child["widgets_values"],
            ["interior_positional.safetensors"],
        )
        self.assertEqual(promoted_indexes, frozenset())

    async def test_named_widget_traversal_is_rejected_before_file_probes(self):
        workflow = {
            "nodes": [
                {
                    "id": 1420,
                    "type": "CheckpointLoaderSimple",
                    "inputs": [
                        {
                            "name": "ckpt_name",
                            "widget": {"name": "ckpt_name"},
                        }
                    ],
                    "widgets_values_named": {
                        "ckpt_name": "../external_named.safetensors",
                    },
                }
            ]
        }

        with (
            patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value=self._checkpoint_paths(
                    Path("synthetic-contained-root")
                ),
            ),
            patch.object(
                Path,
                "exists",
                side_effect=AssertionError(
                    "existence probe must not run before containment"
                ),
            ) as exists_mock,
            patch.object(
                Path,
                "is_file",
                side_effect=AssertionError(
                    "file probe must not run before containment"
                ),
            ) as is_file_mock,
            patch("builtins.open", mock_open()) as open_mock,
        ):
            issues = await model_assets.check_model_assets(
                workflow,
                HealthCheckRequest(
                    workflow=workflow,
                    scope=DiagnosticsScope.MANUAL,
                ),
            )

        self.assertEqual(len(issues), 1)
        serialized = repr(issues[0].to_dict())
        self.assertIn(model_assets.INVALID_ASSET_DISPLAY_NAME, serialized)
        self.assertNotIn("external_named.safetensors", serialized)
        exists_mock.assert_not_called()
        is_file_mock.assert_not_called()
        open_mock.assert_not_called()

    @staticmethod
    def _nested_asset_workflow(
        root_nodes,
        subgraphs,
    ):
        return {
            "nodes": root_nodes,
            "definitions": {"subgraphs": subgraphs},
        }

    @staticmethod
    def _subgraph_definition(
        definition_id,
        nodes,
        *,
        inputs=None,
        links=None,
    ):
        return {
            "id": definition_id,
            "inputs": inputs or [],
            "nodes": nodes,
            "links": links or [],
        }

    @classmethod
    def _promoted_media_workflow(
        cls,
        source_type,
        source_widget,
        *,
        host_positional=None,
        host_named=None,
        source_value="stale-source-value",
    ):
        definition_input_name = "promoted_media"
        host = {
            "id": 240,
            "type": "synthetic-media-subgraph",
            "title": "Visible Media Host",
        }
        if host_positional is not None:
            host["widgets_values"] = [host_positional]
        if host_named is not None:
            host["widgets_values_named"] = {
                definition_input_name: host_named,
            }
        leaf = {
            "id": 9,
            "type": source_type,
            "title": "Concrete Media Loader",
            "inputs": [
                {
                    "name": source_widget,
                    "type": "COMBO",
                    "widget": {"name": source_widget},
                    "link": 1,
                }
            ],
            "widgets_values": [source_value],
        }
        definition = cls._subgraph_definition(
            "synthetic-media-subgraph",
            [leaf],
            inputs=[
                {
                    "id": "synthetic-media-input",
                    "name": definition_input_name,
                    "type": "COMBO",
                    "linkIds": [1],
                }
            ],
            links=[
                {
                    "id": 1,
                    "origin_id": -10,
                    "origin_slot": 0,
                    "target_id": 9,
                    "target_slot": 0,
                    "type": "COMBO",
                }
            ],
        )
        return cls._nested_asset_workflow([host], [definition])

    async def test_promoted_media_preserves_visible_host_and_source_loader(self):
        cases = [
            ("LoadImage", "image", "missing-image.png", "input"),
            ("LoadVideo", "file", "missing-video.mp4", "input"),
            ("LoadAudio", "audio", "missing-audio.wav", "input"),
            (
                "LoadImageOutput",
                "image",
                "generated-image.png [output]",
                "output",
            ),
        ]

        for source_type, source_widget, missing_name, category in cases:
            with self.subTest(source_type=source_type):
                workflow = self._promoted_media_workflow(
                    source_type,
                    source_widget,
                    host_positional=missing_name,
                )
                with patch(
                    "services.diagnostics.checks.model_assets._find_file_in_comfy_paths",
                    return_value=(False, None, None, False),
                ) as find_mock:
                    issues = await model_assets.check_model_assets(
                        workflow,
                        HealthCheckRequest(
                            workflow=workflow,
                            scope=DiagnosticsScope.MANUAL,
                        ),
                    )

                self.assertEqual(len(issues), 1)
                self.assertEqual(issues[0].target.node_id, 240)
                self.assertEqual(issues[0].severity, IssueSeverity.WARNING)
                self.assertEqual(
                    issues[0].metadata["asset_provenance"],
                    {
                        "visible_node_id": 240,
                        "source_execution_id": "240:9",
                        "source_node_id": 9,
                        "source_node_type": source_type,
                        "promoted": True,
                    },
                )
                find_mock.assert_called_once_with(missing_name, category)

    async def test_promoted_media_named_fallback_and_positional_precedence(self):
        cases = [
            {
                "host_positional": None,
                "host_named": "named-fallback.mp4",
                "expected": "named-fallback.mp4",
                "forbidden": "stale-source.mp4",
            },
            {
                "host_positional": "positional-authority.png",
                "host_named": "named-conflict.png",
                "expected": "positional-authority.png",
                "forbidden": "named-conflict.png",
            },
        ]

        for case in cases:
            with self.subTest(expected=case["expected"]):
                workflow = self._promoted_media_workflow(
                    "LoadVideo" if case["expected"].endswith(".mp4") else "LoadImage",
                    "file" if case["expected"].endswith(".mp4") else "image",
                    host_positional=case["host_positional"],
                    host_named=case["host_named"],
                    source_value=case["forbidden"],
                )
                with patch(
                    "services.diagnostics.checks.model_assets._find_file_in_comfy_paths",
                    return_value=(False, None, None, False),
                ):
                    issues = await model_assets.check_model_assets(
                        workflow,
                        HealthCheckRequest(
                            workflow=workflow,
                            scope=DiagnosticsScope.MANUAL,
                        ),
                    )

                self.assertEqual(len(issues), 1)
                serialized = repr(issues[0].to_dict())
                self.assertIn(case["expected"], serialized)
                self.assertNotIn(case["forbidden"], serialized)
                self.assertTrue(
                    issues[0].metadata["asset_provenance"]["promoted"]
                )

    async def test_custom_upload_loader_is_not_inferred_from_media_suffix(self):
        for missing_name in ["unknown-image.png", "unknown-audio.wav"]:
            with self.subTest(missing_name=missing_name):
                workflow = {
                    "nodes": [
                        {
                            "id": 241,
                            "type": "SyntheticCustomNode",
                            "title": "Unknown Custom Node",
                            "widgets_values": [missing_name],
                        }
                    ]
                }
                with patch(
                    "services.diagnostics.checks.model_assets._find_file_in_comfy_paths",
                    side_effect=AssertionError(
                        "unknown media suffix must not imply upload-loader support"
                    ),
                ):
                    issues = await model_assets.check_model_assets(
                        workflow,
                        HealthCheckRequest(
                            workflow=workflow,
                            scope=DiagnosticsScope.MANUAL,
                        ),
                    )

                self.assertEqual(issues, [])

    async def test_nested_non_promoted_asset_preserves_visible_and_source_provenance(self):
        workflow = self._nested_asset_workflow(
            [
                {
                    "id": 140,
                    "type": "synthetic-subgraph",
                    "title": "Visible Synthetic Host",
                    "widgets_values": [],
                }
            ],
            [
                self._subgraph_definition(
                    "synthetic-subgraph",
                    [
                        {
                            "id": 7,
                            "type": "CheckpointLoaderSimple",
                            "title": "Interior Loader",
                            "widgets_values": ["nested_missing.pt2"],
                        }
                    ],
                )
            ],
        )
        request = HealthCheckRequest(
            workflow=workflow,
            scope=DiagnosticsScope.MANUAL,
        )

        with patch(
            "services.diagnostics.checks.model_assets._get_comfy_model_paths",
            return_value=self._checkpoint_paths(Path("synthetic-empty-root")),
        ):
            issues = await model_assets.check_model_assets(workflow, request)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].target.node_id, 140)
        self.assertEqual(issues[0].severity, IssueSeverity.WARNING)
        self.assertEqual(
            issues[0].metadata["asset_provenance"],
            {
                "visible_node_id": 140,
                "source_execution_id": "140:7",
                "source_node_id": 7,
                "source_node_type": "CheckpointLoaderSimple",
                "promoted": False,
            },
        )

    async def test_nested_promoted_value_uses_host_value_and_source_loader(self):
        inputs = [
            {
                "id": "synthetic-ckpt-input",
                "name": "ckpt_name",
                "type": "COMBO",
                "linkIds": [1],
            }
        ]
        inner_host = {
            "id": 8,
            "type": "inner-promoted-subgraph",
            "title": "Inner Promoted Host",
            "inputs": [
                {
                    "name": "ckpt_name",
                    "type": "COMBO",
                    "widget": {"name": "ckpt_name"},
                    "link": 1,
                }
            ],
            "widgets_values": ["stale_interior.safetensors"],
        }
        outer_links = [
            {
                "id": 1,
                "origin_id": -10,
                "origin_slot": 0,
                "target_id": 8,
                "target_slot": 0,
                "type": "COMBO",
            }
        ]
        inner_inputs = [
            {
                "id": "inner-ckpt-input",
                "name": "ckpt_name",
                "type": "COMBO",
                "linkIds": [2],
            }
        ]
        leaf = {
            "id": 9,
            "type": "CheckpointLoaderSimple",
            "title": "Concrete Interior Loader",
            "inputs": [
                {
                    "name": "ckpt_name",
                    "type": "COMBO",
                    "widget": {"name": "ckpt_name"},
                    "link": 2,
                }
            ],
            "widgets_values": ["deep_stale.safetensors"],
        }
        inner_links = [
            {
                "id": 2,
                "origin_id": -10,
                "origin_slot": 0,
                "target_id": 9,
                "target_slot": 0,
                "type": "COMBO",
            }
        ]
        workflow = self._nested_asset_workflow(
            [
                {
                    "id": 141,
                    "type": "promoted-subgraph",
                    "title": "Resolved Shared Host",
                    "widgets_values": ["resolved.safetensors"],
                },
                {
                    "id": 142,
                    "type": "promoted-subgraph",
                    "title": "Missing Shared Host",
                    "widgets_values": ["host_missing.safetensors"],
                },
            ],
            [
                self._subgraph_definition(
                    "promoted-subgraph",
                    [inner_host],
                    inputs=inputs,
                    links=outer_links,
                ),
                self._subgraph_definition(
                    "inner-promoted-subgraph",
                    [leaf],
                    inputs=inner_inputs,
                    links=inner_links,
                ),
            ],
        )
        request = HealthCheckRequest(
            workflow=workflow,
            scope=DiagnosticsScope.MANUAL,
        )

        with tempfile.TemporaryDirectory() as temp_root:
            checkpoint_root = Path(temp_root) / "checkpoints"
            checkpoint_root.mkdir()
            (checkpoint_root / "resolved.safetensors").write_bytes(b"x")
            with patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value=self._checkpoint_paths(checkpoint_root),
            ):
                issues = await model_assets.check_model_assets(
                    workflow,
                    request,
                )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].target.node_id, 142)
        self.assertEqual(issues[0].severity, IssueSeverity.WARNING)
        serialized = repr(issues[0].to_dict())
        self.assertIn("host_missing.safetensors", serialized)
        self.assertNotIn("stale_interior.safetensors", serialized)
        self.assertNotIn("deep_stale.safetensors", serialized)
        self.assertEqual(
            issues[0].metadata["asset_provenance"][
                "source_execution_id"
            ],
            "142:8:9",
        )
        self.assertTrue(
            issues[0].metadata["asset_provenance"]["promoted"]
        )

    async def test_named_widget_promoted_nested_value_preserves_provenance(self):
        definition = self._subgraph_definition(
            "named-promoted-subgraph",
            [
                {
                    "id": 9,
                    "type": "CheckpointLoaderSimple",
                    "title": "Interior Named Loader",
                    "inputs": [
                        {
                            "name": "ckpt_name",
                            "type": "COMBO",
                            "widget": {"name": "ckpt_name"},
                            "link": 1,
                        }
                    ],
                    "widgets_values": ["stale_interior.safetensors"],
                }
            ],
            inputs=[
                {
                    "id": "named-ckpt-input",
                    "name": "ckpt_name",
                    "type": "COMBO",
                    "linkIds": [1],
                }
            ],
            links=[
                {
                    "id": 1,
                    "origin_id": -10,
                    "origin_slot": 0,
                    "target_id": 9,
                    "target_slot": 0,
                    "type": "COMBO",
                }
            ],
        )
        workflow = self._nested_asset_workflow(
            [
                {
                    "id": 142,
                    "type": "named-promoted-subgraph",
                    "title": "Visible Named Host",
                    "widgets_values_named": {
                        "ckpt_name": "named_promoted_missing.safetensors",
                    },
                }
            ],
            [definition],
        )

        with patch(
            "services.diagnostics.checks.model_assets._get_comfy_model_paths",
            return_value=self._checkpoint_paths(Path("synthetic-empty-root")),
        ):
            issues = await model_assets.check_model_assets(
                workflow,
                HealthCheckRequest(
                    workflow=workflow,
                    scope=DiagnosticsScope.MANUAL,
                ),
            )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].target.node_id, 142)
        serialized = repr(issues[0].to_dict())
        self.assertIn("named_promoted_missing.safetensors", serialized)
        self.assertNotIn("stale_interior.safetensors", serialized)
        self.assertEqual(
            issues[0].metadata["asset_provenance"],
            {
                "visible_node_id": 142,
                "source_execution_id": "142:9",
                "source_node_id": 9,
                "source_node_type": "CheckpointLoaderSimple",
                "promoted": True,
            },
        )

    async def test_named_widget_values_obey_path_and_node_budgets(self):
        workflow = {
            "nodes": [
                {
                    "id": index,
                    "type": "CheckpointLoaderSimple",
                    "inputs": [
                        {
                            "name": "ckpt_name",
                            "widget": {"name": "ckpt_name"},
                        }
                    ],
                    "widgets_values_named": {
                        "ckpt_name": f"named_budget_{index}.safetensors",
                    },
                }
                for index in range(4)
            ]
        }
        empty_paths = self._checkpoint_paths(Path("synthetic-empty-root"))

        with (
            patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value=empty_paths,
            ),
            patch.object(model_assets, "MAX_WORKFLOW_NODES", 2),
        ):
            issues = await model_assets.check_model_assets(
                workflow,
                HealthCheckRequest(
                    workflow=workflow,
                    scope=DiagnosticsScope.MANUAL,
                    max_paths=1,
                ),
            )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].target.node_id, 0)

    async def test_shared_subgraph_hosts_keep_instance_specific_findings(self):
        definition = self._subgraph_definition(
            "shared-subgraph",
            [
                {
                    "id": 9,
                    "type": "CheckpointLoaderSimple",
                    "widgets_values": ["shared_missing.sft"],
                }
            ],
        )
        workflow = self._nested_asset_workflow(
            [
                {"id": 143, "type": "shared-subgraph", "widgets_values": []},
                {"id": 144, "type": "shared-subgraph", "widgets_values": []},
            ],
            [definition],
        )
        request = HealthCheckRequest(
            workflow=workflow,
            scope=DiagnosticsScope.MANUAL,
        )

        with patch(
            "services.diagnostics.checks.model_assets._get_comfy_model_paths",
            return_value=self._checkpoint_paths(Path("synthetic-empty-root")),
        ):
            issues = await model_assets.check_model_assets(workflow, request)

        self.assertEqual(
            {issue.target.node_id for issue in issues},
            {143, 144},
        )
        self.assertEqual(
            {
                issue.metadata["asset_provenance"]["source_execution_id"]
                for issue in issues
            },
            {"143:9", "144:9"},
        )

    async def test_nested_traversal_is_cycle_safe(self):
        definition = self._subgraph_definition(
            "cyclic-subgraph",
            [
                {
                    "id": 10,
                    "type": "CheckpointLoaderSimple",
                    "widgets_values": ["cycle_missing.safetensors"],
                },
                {
                    "id": 11,
                    "type": "cyclic-subgraph",
                    "widgets_values": [],
                },
            ],
        )
        workflow = self._nested_asset_workflow(
            [{"id": 145, "type": "cyclic-subgraph", "widgets_values": []}],
            [definition],
        )
        request = HealthCheckRequest(
            workflow=workflow,
            scope=DiagnosticsScope.MANUAL,
        )

        with patch(
            "services.diagnostics.checks.model_assets._get_comfy_model_paths",
            return_value=self._checkpoint_paths(Path("synthetic-empty-root")),
        ):
            issues = await model_assets.check_model_assets(workflow, request)

        self.assertEqual(len(issues), 1)
        self.assertEqual(
            issues[0].metadata["asset_provenance"][
                "source_execution_id"
            ],
            "145:10",
        )

    async def test_malformed_subgraph_collection_is_ignored_safely(self):
        workflow = {
            "nodes": [
                {
                    "id": 1451,
                    "type": "CheckpointLoaderSimple",
                    "widgets_values": ["root_missing.safetensors"],
                }
            ],
            "definitions": {"subgraphs": None},
        }
        request = HealthCheckRequest(
            workflow=workflow,
            scope=DiagnosticsScope.MANUAL,
        )

        with patch(
            "services.diagnostics.checks.model_assets._get_comfy_model_paths",
            return_value=self._checkpoint_paths(Path("synthetic-empty-root")),
        ):
            issues = await model_assets.check_model_assets(workflow, request)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].target.node_id, 1451)

    async def test_nested_traversal_obeys_depth_and_node_budgets(self):
        workflow = self._nested_asset_workflow(
            [{"id": 146, "type": "depth-one", "widgets_values": []}],
            [
                self._subgraph_definition(
                    "depth-one",
                    [{"id": 12, "type": "depth-two", "widgets_values": []}],
                ),
                self._subgraph_definition(
                    "depth-two",
                    [
                        {
                            "id": 13,
                            "type": "CheckpointLoaderSimple",
                            "widgets_values": ["depth_missing.safetensors"],
                        }
                    ],
                ),
            ],
        )
        request = HealthCheckRequest(
            workflow=workflow,
            scope=DiagnosticsScope.MANUAL,
        )
        empty_paths = self._checkpoint_paths(Path("synthetic-empty-root"))

        with (
            patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value=empty_paths,
            ),
            patch.object(model_assets, "MAX_SUBGRAPH_DEPTH", 1),
        ):
            depth_limited = await model_assets.check_model_assets(
                workflow,
                request,
            )

        with (
            patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value=empty_paths,
            ),
            patch.object(model_assets, "MAX_SUBGRAPH_DEPTH", 2),
        ):
            depth_allowed = await model_assets.check_model_assets(
                workflow,
                request,
            )

        many_nodes = {
            "nodes": [
                {
                    "id": index,
                    "type": "CheckpointLoaderSimple",
                    "widgets_values": [f"node_{index}.safetensors"],
                }
                for index in range(5)
            ]
        }
        with (
            patch(
                "services.diagnostics.checks.model_assets._get_comfy_model_paths",
                return_value=empty_paths,
            ),
            patch.object(model_assets, "MAX_WORKFLOW_NODES", 2),
        ):
            node_limited = await model_assets.check_model_assets(
                many_nodes,
                HealthCheckRequest(
                    workflow=many_nodes,
                    scope=DiagnosticsScope.MANUAL,
                    max_paths=10,
                ),
            )

        self.assertEqual(depth_limited, [])
        self.assertEqual(len(depth_allowed), 1)
        self.assertEqual(len(node_limited), 2)

    async def test_model_asset_scan_obeys_and_normalizes_path_budget(self):
        workflow = {
            "nodes": [
                {
                    "id": index,
                    "type": "CheckpointLoaderSimple",
                    "widgets_values": [f"path_{index}.safetensors"],
                }
                for index in range(3)
            ]
        }
        empty_paths = self._checkpoint_paths(Path("synthetic-empty-root"))

        with patch(
            "services.diagnostics.checks.model_assets._get_comfy_model_paths",
            return_value=empty_paths,
        ):
            issues = await model_assets.check_model_assets(
                workflow,
                HealthCheckRequest(
                    workflow=workflow,
                    scope=DiagnosticsScope.MANUAL,
                    max_paths=1,
                ),
            )

        self.assertEqual(len(issues), 1)
        cases = {
            -1: 0,
            0: 0,
            1: 1,
            "2": 2,
            "invalid": model_assets.DEFAULT_MAX_PATHS,
            None: model_assets.DEFAULT_MAX_PATHS,
            10_000: model_assets.MAX_PATH_BUDGET,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(
                    model_assets._normalize_path_budget(value),
                    expected,
                )

    def test_missing_model_prompt_uses_configured_registered_path_guidance(self):
        source = (
            Path(__file__).resolve().parents[1] / "api_routes.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("ComfyUI/models/ folder", source)
        self.assertIn("configured or registered model folder", source)

if __name__ == '__main__':
    unittest.main(verbosity=2)

"""
Unit tests for F14 Diagnostics Checks.
Tests privacy_security and runtime_performance heuristics.
Uses unittest.IsolatedAsyncioTestCase for async compatibility.
"""

import unittest
from unittest.mock import patch, MagicMock
from services.diagnostics.checks import privacy_security, runtime_performance
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

if __name__ == '__main__':
    unittest.main(verbosity=2)

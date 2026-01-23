import os
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

# Add repo root to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import telemetry


class TestTelemetryPaths(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.legacy_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.legacy_dir, ignore_errors=True)

    def test_get_telemetry_path_uses_canonical_dir(self):
        with patch.object(telemetry, "_get_canonical_doctor_data_dir", lambda: self.temp_dir):
            path = telemetry.get_telemetry_path()
            self.assertEqual(path, os.path.join(self.temp_dir, "telemetry.json"))

    def test_migrate_legacy_telemetry_file(self):
        legacy_path = os.path.join(self.legacy_dir, "telemetry.json")
        target_path = os.path.join(self.temp_dir, "telemetry.json")

        payload = [{"schema_version": "1.0", "event_id": "x", "timestamp": "t", "category": "session", "action": "start"}]
        with open(legacy_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        with patch.object(telemetry, "_legacy_telemetry_path", lambda: legacy_path):
            telemetry._migrate_legacy_telemetry_file(target_path)

        self.assertTrue(os.path.exists(target_path))
        with open(target_path, "r", encoding="utf-8") as f:
            migrated = json.load(f)
        self.assertEqual(migrated, payload)

        # legacy renamed
        self.assertFalse(os.path.exists(legacy_path))
        renamed = [p for p in os.listdir(self.legacy_dir) if p.startswith("telemetry.json.migrated-")]
        self.assertEqual(len(renamed), 1)


if __name__ == "__main__":
    unittest.main()



import unittest
import tempfile
import shutil
import os
import sys
import json
from unittest.mock import patch

# Ensure we can import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import module under test
import logger

class TestR18Migration(unittest.TestCase):
    
    def setUp(self):
        # Create separate temp dirs for legacy (logs) and new (data)
        self.test_root = tempfile.mkdtemp()
        self.legacy_logs_dir = os.path.join(self.test_root, "logs")
        os.makedirs(self.legacy_logs_dir, exist_ok=True)
        
        self.new_data_dir = os.path.join(self.test_root, "new_doctor_data")
        os.makedirs(self.new_data_dir, exist_ok=True)
        
    def tearDown(self):
        shutil.rmtree(self.test_root)

    def test_migrate_legacy_data_success(self):
        """Test successful migration from legacy to new path."""
        # 1. Setup legacy file
        legacy_file = os.path.join(self.legacy_logs_dir, "error_history.json")
        legacy_content = [{"timestamp": "2023-01-01T00:00:00", "error": "test legacy error"}]
        
        with open(legacy_file, 'w', encoding='utf-8') as f:
            json.dump(legacy_content, f)
            
        target_file = os.path.join(self.new_data_dir, "error_history.json")
        
        # 2. Patch dependencies
        # IMPORTANT: _history_file is computed at import time, so we must patch it directly
        # patching get_doctor_data_dir() is not enough effectively.
        with patch('logger.doctor_paths', object()), \
             patch('logger._current_dir', self.test_root), \
             patch('logger._history_file', target_file):
             
             # 3. Execute migration
             logger._migrate_legacy_data()
             
             # 4. Verify target exists and matches content
             self.assertTrue(os.path.exists(target_file), "Target file should exist")
             with open(target_file, 'r') as f:
                 data = json.load(f)
                 self.assertEqual(data[0]["error"], "test legacy error")
                 
             # 5. Verify legacy file is renamed (not deleted)
             self.assertFalse(os.path.exists(legacy_file), "Legacy file should have been renamed")
             
             # Check for renamed file
             files = os.listdir(self.legacy_logs_dir)
             renamed_files = [f for f in files if f.startswith("error_history.json.migrated-")]
             self.assertEqual(len(renamed_files), 1, "Should have exactly one migrated backup file")

    def test_migrate_legacy_data_idempotency(self):
        """Test migration is skipped if target already exists."""
        # 1. Setup legacy file
        legacy_file = os.path.join(self.legacy_logs_dir, "error_history.json")
        with open(legacy_file, 'w', encoding='utf-8') as f:
            f.write("legacy content")
            
        # 2. Setup EXISTING target file
        target_file = os.path.join(self.new_data_dir, "error_history.json")
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write("existing new content")
            
        with patch('logger.doctor_paths', object()), \
             patch('logger._current_dir', self.test_root), \
             patch('logger._history_file', target_file):
             
             # 3. Execute migration
             logger._migrate_legacy_data()
             
             # 4. Verify target is UNTOUCHED
             with open(target_file, 'r') as f:
                 content = f.read()
                 self.assertEqual(content, "existing new content")
                 
             # 5. Verify legacy is UNTOUCHED
             self.assertTrue(os.path.exists(legacy_file))

if __name__ == '__main__':
    unittest.main()

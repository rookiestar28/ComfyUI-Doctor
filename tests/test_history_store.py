"""
Tests for HistoryStore - error history persistence.
"""
import unittest
import os
import sys
import json
import tempfile
import shutil

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from history_store import HistoryStore, HistoryEntry


class TestHistoryEntry(unittest.TestCase):
    """Tests for HistoryEntry dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        entry = HistoryEntry(
            timestamp="2025-12-29T14:00:00",
            error="Test error",
            suggestion={"pattern": "test", "message": "Test suggestion"},
            node_context={"node_id": "42"},
        )
        
        result = entry.to_dict()
        
        self.assertEqual(result["timestamp"], "2025-12-29T14:00:00")
        self.assertEqual(result["error"], "Test error")
        self.assertEqual(result["suggestion"]["pattern"], "test")
        self.assertEqual(result["node_context"]["node_id"], "42")
        self.assertIsNone(result["workflow_snapshot"])
    
    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "timestamp": "2025-12-29T14:00:00",
            "error": "Test error",
            "suggestion": {"pattern": "test"},
            "node_context": None,
            "workflow_snapshot": "workflow_json",
        }
        
        entry = HistoryEntry.from_dict(data)
        
        self.assertEqual(entry.timestamp, "2025-12-29T14:00:00")
        self.assertEqual(entry.error, "Test error")
        self.assertEqual(entry.suggestion["pattern"], "test")
        self.assertIsNone(entry.node_context)
        self.assertEqual(entry.workflow_snapshot, "workflow_json")
    
    def test_from_dict_with_missing_fields(self):
        """Test creation from partial dictionary."""
        data = {"timestamp": "2025-12-29T14:00:00"}
        
        entry = HistoryEntry.from_dict(data)
        
        self.assertEqual(entry.timestamp, "2025-12-29T14:00:00")
        self.assertEqual(entry.error, "")
        self.assertEqual(entry.suggestion, {})


class TestHistoryStore(unittest.TestCase):
    """Tests for HistoryStore persistence."""
    
    def setUp(self):
        """Create a temporary directory for tests."""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "test_history.json")
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)
    
    def test_append_and_get_all(self):
        """Test appending entries and retrieving all."""
        store = HistoryStore(self.test_file, maxlen=10)
        
        entry1 = HistoryEntry(
            timestamp="2025-12-29T14:00:00",
            error="Error 1",
            suggestion={},
        )
        entry2 = HistoryEntry(
            timestamp="2025-12-29T14:01:00",
            error="Error 2",
            suggestion={},
        )
        
        store.append(entry1)
        store.append(entry2)
        
        history = store.get_all()
        
        self.assertEqual(len(history), 2)
        # get_all returns newest first
        self.assertEqual(history[0]["error"], "Error 2")
        self.assertEqual(history[1]["error"], "Error 1")
    
    def test_persistence_across_instances(self):
        """Test that history persists across store instances."""
        store1 = HistoryStore(self.test_file, maxlen=10)
        entry = HistoryEntry(
            timestamp="2025-12-29T14:00:00",
            error="Persistent error",
            suggestion={"test": True},
        )
        store1.append(entry)
        
        # Create new instance pointing to same file
        store2 = HistoryStore(self.test_file, maxlen=10)
        history = store2.get_all()
        
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["error"], "Persistent error")
    
    def test_maxlen_enforcement(self):
        """Test that maxlen is enforced."""
        store = HistoryStore(self.test_file, maxlen=3)
        
        for i in range(5):
            entry = HistoryEntry(
                timestamp=f"2025-12-29T14:0{i}:00",
                error=f"Error {i}",
                suggestion={},
            )
            store.append(entry)
        
        history = store.get_all()
        
        self.assertEqual(len(history), 3)
        # Should contain the last 3 entries (Error 2, 3, 4)
        self.assertEqual(history[0]["error"], "Error 4")
        self.assertEqual(history[1]["error"], "Error 3")
        self.assertEqual(history[2]["error"], "Error 2")
    
    def test_clear(self):
        """Test clearing history."""
        store = HistoryStore(self.test_file, maxlen=10)
        entry = HistoryEntry(
            timestamp="2025-12-29T14:00:00",
            error="Error",
            suggestion={},
        )
        store.append(entry)
        
        store.clear()
        
        self.assertEqual(len(store), 0)
        self.assertEqual(store.get_all(), [])
    
    def test_get_latest(self):
        """Test getting the latest entry."""
        store = HistoryStore(self.test_file, maxlen=10)
        
        # Empty store
        self.assertIsNone(store.get_latest())
        
        entry1 = HistoryEntry(
            timestamp="2025-12-29T14:00:00",
            error="Error 1",
            suggestion={},
        )
        entry2 = HistoryEntry(
            timestamp="2025-12-29T14:01:00",
            error="Error 2",
            suggestion={},
        )
        
        store.append(entry1)
        store.append(entry2)
        
        latest = store.get_latest()
        
        self.assertEqual(latest["error"], "Error 2")
    
    def test_handles_corrupted_file(self):
        """Test handling of corrupted JSON file."""
        # Write invalid JSON
        with open(self.test_file, "w") as f:
            f.write("not valid json {{{")
        
        # Should not raise, just start with empty history
        store = HistoryStore(self.test_file, maxlen=10)
        history = store.get_all()
        
        self.assertEqual(history, [])
    
    def test_len(self):
        """Test __len__ method."""
        store = HistoryStore(self.test_file, maxlen=10)
        
        self.assertEqual(len(store), 0)
        
        entry = HistoryEntry(
            timestamp="2025-12-29T14:00:00",
            error="Error",
            suggestion={},
        )
        store.append(entry)
        
        self.assertEqual(len(store), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)

"""
Unit tests for PatternLoader (STAGE 2).

Tests the JSON-based error pattern loader with hot-reload capability.
"""

import os
import sys
import json
import time
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pattern_loader import PatternLoader, reset_pattern_loader


def test_load_valid_json():
    """Test 1: Load valid pattern JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test pattern file
        pattern_file = Path(tmpdir) / "test.json"
        test_data = {
            "version": "1.0.0",
            "patterns": [
                {
                    "id": "test_pattern",
                    "regex": "TestError: (.+)",
                    "error_key": "TEST_ERROR",
                    "has_groups": True,
                    "priority": 50,
                    "category": "generic",
                    "tags": ["test"],
                    "notes": "Test pattern"
                }
            ]
        }

        with open(pattern_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)

        # Load patterns
        loader = PatternLoader([tmpdir])
        count = loader.load()

        assert count == 1, f"Expected 1 pattern, got {count}"
        assert len(loader.compiled_patterns) == 1
        print("✅ Test 1 passed: Load valid JSON")


def test_schema_validation():
    """Test 2: Schema validation rejects invalid patterns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Missing required field 'priority'
        pattern_file = Path(tmpdir) / "invalid.json"
        invalid_data = {
            "version": "1.0.0",
            "patterns": [
                {
                    "id": "invalid_pattern",
                    "regex": "TestError",
                    "error_key": "TEST_ERROR",
                    "category": "generic"
                    # Missing 'priority' field
                }
            ]
        }

        with open(pattern_file, 'w', encoding='utf-8') as f:
            json.dump(invalid_data, f)

        loader = PatternLoader([tmpdir])
        count = loader.load()  # Should skip invalid pattern

        assert count == 0, f"Expected 0 patterns (invalid rejected), got {count}"
        print("✅ Test 2 passed: Schema validation")


def test_pattern_matching():
    """Test 3: Pattern matching works correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pattern_file = Path(tmpdir) / "test.json"
        test_data = {
            "version": "1.0.0",
            "patterns": [
                {
                    "id": "cuda_oom",
                    "regex": "CUDA out of memory",
                    "error_key": "OOM",
                    "has_groups": False,
                    "priority": 90,
                    "category": "memory"
                }
            ]
        }

        with open(pattern_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)

        loader = PatternLoader([tmpdir])
        loader.load()

        # Test match
        error_text = "RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB"
        result = loader.match(error_text)

        assert result is not None, "Pattern should match CUDA OOM error"
        error_key, groups = result
        assert error_key == "OOM"
        assert groups == []
        print("✅ Test 3 passed: Pattern matching")


def test_priority_sorting():
    """Test 4: Higher priority patterns checked first."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pattern_file = Path(tmpdir) / "test.json"
        test_data = {
            "version": "1.0.0",
            "patterns": [
                {
                    "id": "low_priority",
                    "regex": "Error",
                    "error_key": "LOW",
                    "has_groups": False,
                    "priority": 10,
                    "category": "generic"
                },
                {
                    "id": "high_priority",
                    "regex": "SpecificError",
                    "error_key": "HIGH",
                    "has_groups": False,
                    "priority": 90,
                    "category": "generic"
                }
            ]
        }

        with open(pattern_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)

        loader = PatternLoader([tmpdir])
        loader.load()

        # "SpecificError" matches both patterns, but high priority should win
        result = loader.match("SpecificError occurred")
        error_key, _ = result
        assert error_key == "HIGH", "High priority pattern should match first"
        print("✅ Test 4 passed: Priority sorting")


def test_hot_reload():
    """Test 5: Hot-reload detects file changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pattern_file = Path(tmpdir) / "test.json"

        # Initial data
        initial_data = {
            "version": "1.0.0",
            "patterns": [
                {
                    "id": "pattern1",
                    "regex": "Pattern1",
                    "error_key": "P1",
                    "has_groups": False,
                    "priority": 50,
                    "category": "generic"
                }
            ]
        }

        with open(pattern_file, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f)

        loader = PatternLoader([tmpdir])
        loader.load()
        assert len(loader.patterns) == 1

        # Wait to ensure mtime changes
        time.sleep(1.1)

        # Modify file
        updated_data = {
            "version": "1.0.0",
            "patterns": [
                {
                    "id": "pattern1",
                    "regex": "Pattern1",
                    "error_key": "P1",
                    "has_groups": False,
                    "priority": 50,
                    "category": "generic"
                },
                {
                    "id": "pattern2",
                    "regex": "Pattern2",
                    "error_key": "P2",
                    "has_groups": False,
                    "priority": 50,
                    "category": "generic"
                }
            ]
        }

        with open(pattern_file, 'w', encoding='utf-8') as f:
            json.dump(updated_data, f)

        # Reload
        reloaded = loader.reload_if_changed()
        assert reloaded is True, "Should detect file change"
        assert len(loader.patterns) == 2, "Should have 2 patterns after reload"
        print("✅ Test 5 passed: Hot-reload")


def test_fallback_on_error():
    """Test 6: Graceful handling of loading errors."""
    # Non-existent directory
    loader = PatternLoader(["/nonexistent/path"])
    count = loader.load()

    assert count == 0, "Should handle non-existent directory gracefully"
    print("✅ Test 6 passed: Fallback on error")


def test_multiple_directories():
    """Test 7: Merge patterns from multiple directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dir1 = Path(tmpdir) / "dir1"
        dir2 = Path(tmpdir) / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        # File in dir1
        file1 = dir1 / "patterns1.json"
        data1 = {
            "version": "1.0.0",
            "patterns": [
                {
                    "id": "p1",
                    "regex": "P1",
                    "error_key": "P1",
                    "has_groups": False,
                    "priority": 50,
                    "category": "generic"
                }
            ]
        }
        with open(file1, 'w') as f:
            json.dump(data1, f)

        # File in dir2
        file2 = dir2 / "patterns2.json"
        data2 = {
            "version": "1.0.0",
            "patterns": [
                {
                    "id": "p2",
                    "regex": "P2",
                    "error_key": "P2",
                    "has_groups": False,
                    "priority": 60,
                    "category": "generic"
                }
            ]
        }
        with open(file2, 'w') as f:
            json.dump(data2, f)

        loader = PatternLoader([str(dir1), str(dir2)])
        count = loader.load()

        assert count == 2, f"Expected 2 patterns from 2 directories, got {count}"
        print("✅ Test 7 passed: Multiple directories")


def test_duplicate_id_detection():
    """Test 8: Reject duplicate pattern IDs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pattern_file = Path(tmpdir) / "duplicate.json"
        duplicate_data = {
            "version": "1.0.0",
            "patterns": [
                {
                    "id": "duplicate_id",
                    "regex": "Pattern1",
                    "error_key": "P1",
                    "has_groups": False,
                    "priority": 50,
                    "category": "generic"
                },
                {
                    "id": "duplicate_id",  # Same ID
                    "regex": "Pattern2",
                    "error_key": "P2",
                    "has_groups": False,
                    "priority": 50,
                    "category": "generic"
                }
            ]
        }

        with open(pattern_file, 'w', encoding='utf-8') as f:
            json.dump(duplicate_data, f)

        loader = PatternLoader([tmpdir])
        count = loader.load()  # Should reject file due to validation error

        assert count == 0, "Should reject file with duplicate IDs"
        print("✅ Test 8 passed: Duplicate ID detection")


def test_real_patterns_load():
    """Test 9: Load actual patterns/builtin/core.json."""
    from pattern_loader import get_pattern_loader, reset_pattern_loader

    # Reset to force fresh load
    reset_pattern_loader()

    # Get loader (will load from actual patterns/ directory)
    loader = get_pattern_loader()

    # Should have 21 patterns from core.json
    stats = loader.get_stats()
    assert stats["total"] >= 21, f"Expected at least 21 patterns, got {stats['total']}"
    assert "builtin" in str(stats["sources"]) or "core.json" in str(stats["sources"])

    print(f"✅ Test 9 passed: Real patterns loaded ({stats['total']} total)")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🧪 PatternLoader Tests (STAGE 2)")
    print("=" * 70 + "\n")

    try:
        test_load_valid_json()
        test_schema_validation()
        test_pattern_matching()
        test_priority_sorting()
        test_hot_reload()
        test_fallback_on_error()
        test_multiple_directories()
        test_duplicate_id_detection()
        test_real_patterns_load()

        print("\n" + "=" * 70)
        print("🎉 All PatternLoader tests passed!")
        print("=" * 70 + "\n")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

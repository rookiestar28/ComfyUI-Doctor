"""
Pattern Validation Test Suite

Tests to ensure all error patterns are syntactically correct and complete.
Validates JSON schema, regex syntax, i18n completeness, and metadata.

Run: pytest tests/test_pattern_validation.py -v

═══════════════════════════════════════════════════════════════════════════
⚠️ CRITICAL: Field Name Consistency Warning
═══════════════════════════════════════════════════════════════════════════
This test suite validates JSON pattern files against the schema.

IMPORTANT: JSON Schema Field Names (DO NOT CHANGE):
  - patterns/schema.json uses "regex" (NOT "pattern")
  - patterns/schema.json uses "error_key" (NOT "suggestion_key")

Common Mistake:
  ❌ required_fields = ["id", "pattern", "suggestion_key", ...]
  ✅ required_fields = ["id", "regex", "error_key", ...]

If tests fail with "missing required field", check that test expectations
match the actual schema definition in patterns/schema.json.

Last Modified: 2026-01-03 (Fixed field name mismatch)
═══════════════════════════════════════════════════════════════════════════
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set

import pytest

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
PATTERNS_DIR = PROJECT_ROOT / "patterns"
SCHEMA_PATH = PATTERNS_DIR / "schema.json"
I18N_PATH = PROJECT_ROOT / "i18n.py"

# Expected languages
SUPPORTED_LANGUAGES = ["en", "zh_TW", "zh_CN", "ja", "de", "fr", "it", "es", "ko"]

# Valid categories
VALID_CATEGORIES = {
    "data_type",
    "framework",
    "memory",
    "model_loading",
    "custom_nodes",
    "workflow",
    "generic"
}


def load_all_pattern_files() -> List[Path]:
    """Load all JSON pattern files from patterns/ directory."""
    pattern_files = []
    for pattern_type in ["builtin", "community"]:
        pattern_dir = PATTERNS_DIR / pattern_type
        if pattern_dir.exists():
            pattern_files.extend(pattern_dir.glob("*.json"))
    return pattern_files


def load_pattern_file(file_path: Path) -> Dict:
    """Load and parse a single pattern JSON file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_error_keys_from_i18n() -> Dict[str, str]:
    """
    Extract ERROR_KEYS mapping from i18n.py.

    Returns:
        Dict mapping uppercase keys to lowercase suggestion keys.
        Example: {"TYPE_MISMATCH": "type_mismatch", "CUDNN_ERROR": "cudnn_error", ...}
    """
    with open(I18N_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Find ERROR_KEYS dictionary
    start = content.find("ERROR_KEYS = {")
    if start == -1:
        return {}

    # Extract key-value pairs (simplified parsing)
    error_keys_dict = {}
    lines = content[start:].split("\n")
    for line in lines:
        if '"' in line and ":" in line:
            # Extract key-value from line like: "TYPE_MISMATCH": "type_mismatch",
            match = re.search(r'"([^"]+)":\s*"([^"]+)"', line)
            if match:
                error_keys_dict[match.group(1)] = match.group(2)
        if line.strip() == "}":
            break
    return error_keys_dict


def extract_suggestions_from_i18n() -> Dict[str, Set[str]]:
    """Extract all SUGGESTIONS keys for each language from i18n.py"""
    with open(I18N_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    
    suggestions_by_lang = {}
    
    # Find SUGGESTIONS dictionary
    start = content.find("SUGGESTIONS")
    if start == -1:
        return suggestions_by_lang
    
    # Extract suggestions for each language
    for lang in SUPPORTED_LANGUAGES:
        lang_start = content.find(f'"{lang}":', start)
        if lang_start == -1:
            continue
        
        keys = set()
        lines = content[lang_start:].split("\n")
        brace_count = 0
        started = False
        
        for line in lines:
            if "{" in line:
                brace_count += line.count("{")
                started = True
            if "}" in line:
                brace_count -= line.count("}")
            
            if started and '"' in line and ":" in line:
                match = re.search(r'"([^"]+)":\s*"', line)
                if match:
                    keys.add(match.group(1))
            
            if started and brace_count == 0:
                break
        
        suggestions_by_lang[lang] = keys
    
    return suggestions_by_lang


class TestPatternValidation:
    """Pattern validation test suite"""
    
    @pytest.fixture(scope="class")
    def all_patterns(self):
        """Load all patterns from all JSON files"""
        all_patterns = []
        for file_path in load_all_pattern_files():
            data = load_pattern_file(file_path)
            for pattern in data.get("patterns", []):
                pattern["_source_file"] = str(file_path.relative_to(PROJECT_ROOT))
                all_patterns.append(pattern)
        return all_patterns
    
    @pytest.fixture(scope="class")
    def error_keys(self):
        """Extract ERROR_KEYS from i18n.py"""
        return extract_error_keys_from_i18n()
    
    @pytest.fixture(scope="class")
    def suggestions(self):
        """Extract SUGGESTIONS from i18n.py"""
        return extract_suggestions_from_i18n()
    
    def test_all_patterns_valid_json(self):
        """Test 1: All pattern files are valid JSON"""
        for file_path in load_all_pattern_files():
            try:
                load_pattern_file(file_path)
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in {file_path}: {e}")
    
    def test_all_patterns_have_required_fields(self, all_patterns):
        """Test 2: All patterns have required fields"""
        # ⚠️ CRITICAL: These field names MUST match patterns/schema.json
        # DO NOT change "regex" to "pattern" or "error_key" to "suggestion_key"
        # See file docstring for detailed explanation
        required_fields = ["id", "regex", "error_key", "priority", "category"]

        for pattern in all_patterns:
            for field in required_fields:
                assert field in pattern, (
                    f"Pattern {pattern.get('id', 'UNKNOWN')} in {pattern['_source_file']} "
                    f"missing required field: {field}"
                )
    
    def test_all_regex_compile(self, all_patterns):
        """Test 3: All regex patterns compile successfully"""
        for pattern in all_patterns:
            pattern_id = pattern.get("id", "UNKNOWN")
            # ⚠️ CRITICAL: Use "regex" (schema field name), NOT "pattern"
            regex_str = pattern.get("regex", "")

            try:
                re.compile(regex_str)
            except re.error as e:
                pytest.fail(
                    f"Pattern {pattern_id} in {pattern['_source_file']} "
                    f"has invalid regex: {e}"
                )

    def test_all_suggestions_exist(self, all_patterns, error_keys, suggestions):
        """Test 4: All error_key values exist in i18n.py ERROR_KEYS and SUGGESTIONS"""
        # Check ERROR_KEYS mapping
        for pattern in all_patterns:
            pattern_id = pattern.get("id", "UNKNOWN")
            # ⚠️ CRITICAL: Use "error_key" (schema field name), NOT "suggestion_key"
            error_key = pattern.get("error_key", "")

            assert error_key in error_keys, (
                f"Pattern {pattern_id} in {pattern['_source_file']} "
                f"has error_key '{error_key}' not found in ERROR_KEYS"
            )

        # Check all languages have translations
        for lang in SUPPORTED_LANGUAGES:
            assert lang in suggestions, f"Language '{lang}' not found in SUGGESTIONS"

            for pattern in all_patterns:
                pattern_id = pattern.get("id", "UNKNOWN")
                error_key = pattern.get("error_key", "")

                # Get the suggestion key from ERROR_KEYS mapping
                # Example: error_key="CUDNN_ERROR" -> suggestion_key="cudnn_error"
                suggestion_key = error_keys.get(error_key, "")

                assert suggestion_key in suggestions[lang], (
                    f"Pattern {pattern_id} (error_key: {error_key}) missing {lang} translation. "
                    f"Expected suggestion key '{suggestion_key}' in SUGGESTIONS['{lang}']"
                )
    
    def test_priority_ranges(self, all_patterns):
        """Test 5: All priorities are within valid range 0-100"""
        for pattern in all_patterns:
            pattern_id = pattern.get("id", "UNKNOWN")
            priority = pattern.get("priority", 0)
            
            assert isinstance(priority, int), (
                f"Pattern {pattern_id} in {pattern['_source_file']} "
                f"has non-integer priority: {priority}"
            )
            
            assert 0 <= priority <= 100, (
                f"Pattern {pattern_id} in {pattern['_source_file']} "
                f"has priority {priority} outside valid range 0-100"
            )
    
    def test_no_duplicate_ids(self, all_patterns):
        """Test 6: No duplicate pattern IDs"""
        seen_ids = {}
        
        for pattern in all_patterns:
            pattern_id = pattern.get("id", "UNKNOWN")
            source_file = pattern["_source_file"]
            
            if pattern_id in seen_ids:
                pytest.fail(
                    f"Duplicate pattern ID '{pattern_id}' found in:\n"
                    f"  - {seen_ids[pattern_id]}\n"
                    f"  - {source_file}"
                )
            
            seen_ids[pattern_id] = source_file
    
    def test_category_validity(self, all_patterns):
        """Test 7: All categories are valid"""
        for pattern in all_patterns:
            pattern_id = pattern.get("id", "UNKNOWN")
            category = pattern.get("category", "")
            
            assert category in VALID_CATEGORIES, (
                f"Pattern {pattern_id} in {pattern['_source_file']} "
                f"has invalid category '{category}'. "
                f"Valid categories: {', '.join(sorted(VALID_CATEGORIES))}"
            )
    
    def test_pattern_statistics(self, all_patterns):
        """Test 8: Print pattern statistics (always passes)"""
        total = len(all_patterns)
        by_category = {}
        by_source = {}
        
        for pattern in all_patterns:
            category = pattern.get("category", "unknown")
            source_file = pattern["_source_file"]
            
            by_category[category] = by_category.get(category, 0) + 1
            by_source[source_file] = by_source.get(source_file, 0) + 1
        
        print(f"\n{'='*60}")
        print(f"Pattern Statistics")
        print(f"{'='*60}")
        print(f"Total patterns: {total}")
        print(f"\nBy category:")
        for cat, count in sorted(by_category.items()):
            print(f"  {cat:20s}: {count}")
        print(f"\nBy source file:")
        for src, count in sorted(by_source.items()):
            print(f"  {src:40s}: {count}")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

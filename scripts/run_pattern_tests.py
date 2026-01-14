"""
Simple test runner for pattern validation (bypasses pytest collection issues)
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import test functions
from tests.test_pattern_validation import (
    load_all_pattern_files,
    load_pattern_file,
    extract_error_keys_from_i18n,
    extract_suggestions_from_i18n,
    SUPPORTED_LANGUAGES,
    VALID_CATEGORIES,
    PROJECT_ROOT
)
import re

def run_tests():
    """Run all validation tests"""
    print("="*70)
    print("Pattern Validation Test Suite")
    print("="*70)
    
    # Load data
    print("\n📂 Loading pattern files...")
    pattern_files = load_all_pattern_files()
    print(f"   Found {len(pattern_files)} pattern files")
    
    all_patterns = []
    for file_path in pattern_files:
        data = load_pattern_file(file_path)
        for pattern in data.get("patterns", []):
            pattern["_source_file"] = str(file_path.relative_to(PROJECT_ROOT))
            all_patterns.append(pattern)
    
    print(f"   Loaded {len(all_patterns)} patterns total")
    
    print("\n📖 Loading i18n data...")
    error_keys = extract_error_keys_from_i18n()
    suggestions = extract_suggestions_from_i18n()
    print(f"   Found {len(error_keys)} error keys")
    print(f"   Found translations for {len(suggestions)} languages")
    
    # Test 1: JSON validity
    print("\n✓ Test 1: JSON Validity")
    for file_path in pattern_files:
        try:
            load_pattern_file(file_path)
            print(f"   ✅ {file_path.name}")
        except Exception as e:
            print(f"   ❌ {file_path.name}: {e}")
            return False
    
    # Test 2: Required fields
    print("\n✓ Test 2: Required Fields")
    required_fields = ["id", "regex", "error_key", "priority", "category"]
    for pattern in all_patterns:
        for field in required_fields:
            if field not in pattern:
                print(f"   ❌ Pattern {pattern.get('id', 'UNKNOWN')} missing field: {field}")
                return False
    print(f"   ✅ All {len(all_patterns)} patterns have required fields")
    
    # Test 3: Regex compilation
    print("\n✓ Test 3: Regex Compilation")
    for pattern in all_patterns:
        try:
            re.compile(pattern.get("regex", ""))
        except re.error as e:
            print(f"   ❌ Pattern {pattern.get('id', 'UNKNOWN')}: Invalid regex - {e}")
            return False
    print(f"   ✅ All {len(all_patterns)} regex patterns compile successfully")
    
    # Test 4: i18n completeness (FIXED: properly map error_key → ERROR_KEYS → SUGGESTIONS)
    print("\n✓ Test 4: i18n Completeness")
    
    # Import ERROR_KEYS dict for proper mapping
    import i18n
    ERROR_KEYS_DICT = i18n.ERROR_KEYS
    
    # First check: all pattern error_keys must exist in ERROR_KEYS
    for pattern in all_patterns:
        error_key = pattern.get("error_key", "")
        if error_key not in ERROR_KEYS_DICT:
            print(f"   ❌ Pattern {pattern.get('id', 'UNKNOWN')}: error_key '{error_key}' not in i18n.ERROR_KEYS")
            return False
    
    # Second check: all mapped suggestion_keys must have translations in all languages
    for lang in SUPPORTED_LANGUAGES:
        if lang not in suggestions:
            print(f"   ❌ Language '{lang}' not found in SUGGESTIONS")
            return False
        
        missing_patterns = []
        for pattern in all_patterns:
            error_key = pattern.get("error_key", "")
            # Map error_key to actual suggestion_key via ERROR_KEYS dict
            # Example: "TYPE_MISMATCH" → "type_mismatch"
            suggestion_key = ERROR_KEYS_DICT.get(error_key)
            
            if suggestion_key is None:
                # Shouldn't happen since we checked above
                missing_patterns.append(f"{pattern.get('id', 'UNKNOWN')} (no mapping for '{error_key}')")
                continue
            
            # Check if the mapped suggestion_key exists in this language's SUGGESTIONS
            if suggestion_key not in suggestions[lang]:
                missing_patterns.append(f"{pattern.get('id', 'UNKNOWN')} ({error_key} → {suggestion_key})")
        
        if missing_patterns:
            print(f"   ❌ {lang}: {len(missing_patterns)} patterns missing translations:")
            for mp in missing_patterns[:5]:  # Show first 5
                print(f"      - {mp}")
            if len(missing_patterns) > 5:
                print(f"      ... and {len(missing_patterns) - 5} more")
            return False
        else:
            print(f"   ✅ {lang}: All {len(all_patterns)} patterns have translations")
    
    # Test 5: Priority ranges
    print("\n✓ Test 5: Priority Ranges (50-95)")
    for pattern in all_patterns:
        priority = pattern.get("priority", 0)
        if not isinstance(priority, int) or not (50 <= priority <= 95):
            print(f"   ❌ Pattern {pattern.get('id', 'UNKNOWN')}: Invalid priority {priority}")
            return False
    print(f"   ✅ All priorities valid")
    
    # Test 6: Unique IDs
    print("\n✓ Test 6: Unique Pattern IDs")
    seen_ids = {}
    for pattern in all_patterns:
        pattern_id = pattern.get("id", "UNKNOWN")
        if pattern_id in seen_ids:
            print(f"   ❌ Duplicate ID '{pattern_id}' in:")
            print(f"      - {seen_ids[pattern_id]}")
            print(f"      - {pattern['_source_file']}")
            return False
        seen_ids[pattern_id] = pattern["_source_file"]
    print(f"   ✅ All {len(all_patterns)} pattern IDs are unique")
    
    # Test 7: Valid categories
    print("\n✓ Test 7: Valid Categories")
    for pattern in all_patterns:
        category = pattern.get("category", "")
        if category not in VALID_CATEGORIES:
            print(f"   ❌ Pattern {pattern.get('id', 'UNKNOWN')}: Invalid category '{category}'")
            print(f"      Valid: {', '.join(sorted(VALID_CATEGORIES))}")
            return False
    print(f"   ✅ All categories valid")
    
    # Statistics
    print("\n📊 Pattern Statistics")
    print("="*70)
    print(f"Total patterns: {len(all_patterns)}")
    
    by_category = {}
    by_source = {}
    for pattern in all_patterns:
        category = pattern.get("category", "unknown")
        source_file = pattern["_source_file"]
        by_category[category] = by_category.get(category, 0) + 1
        by_source[source_file] = by_source.get(source_file, 0) + 1
    
    print("\nBy category:")
    for cat, count in sorted(by_category.items()):
        print(f"  {cat:20s}: {count}")
    
    print("\nBy source file:")
    for src, count in sorted(by_source.items()):
        print(f"  {src:40s}: {count}")
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED!")
    print("="*70)
    return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

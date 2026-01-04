"""
JSON-based Error Pattern Loader with Hot-Reload Support.

Loads error pattern definitions from JSON files and provides pattern matching
with priority-based ordering and hot-reload capability.

Architecture:
- Load patterns from multiple JSON directories (builtin, community, custom)
- Priority-based sorting (higher priority patterns checked first)
- Hot-reload support (detects file changes without restart)
- Schema validation for pattern files
- Graceful fallback on loading errors

Usage:
    loader = get_pattern_loader()
    result = loader.match(error_traceback)
    if result:
        error_key, captured_groups = result
"""

import json
import re
import os
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Relative import with fallback for tests
try:
    pass  # No internal dependencies yet
except ImportError:
    pass

logger = logging.getLogger(__name__)


class PatternLoader:
    """
    JSON-based error pattern loader with hot-reload capability.

    Features:
    - Load patterns from multiple JSON files
    - Priority-based sorting (high priority checked first)
    - Hot-reload without restart
    - Schema validation
    - Merge strategy for community patterns
    """

    def __init__(self, pattern_dirs: List[str]):
        """
        Initialize loader with pattern directories.

        Args:
            pattern_dirs: List of directories to search for *.json files
                         Priority order: builtin.json > community.json > custom.json
        """
        self.pattern_dirs = [Path(d) for d in pattern_dirs]
        self.patterns: List[Dict] = []
        self.compiled_patterns: List[Tuple[re.Pattern, str, bool, int]] = []
        self._file_mtimes: Dict[Path, float] = {}

    def get_pattern_info(self, pattern_id: str) -> Optional[Dict]:
        """
        Get full metadata for a pattern by ID.

        Args:
            pattern_id: The ID of the pattern to look up

        Returns:
            Dictionary with pattern metadata (id, category, priority) or None if not found
        """
        for pattern in self.patterns:
            if pattern.get("id") == pattern_id:
                return {
                    "id": pattern.get("id"),
                    "category": pattern.get("category"),
                    "priority": pattern.get("priority")
                }
        return None

    def load(self, validate_schema: bool = True) -> int:
        """
        Load all patterns from JSON files.

        Args:
            validate_schema: Whether to validate JSON schema (default: True)

        Returns:
            Number of patterns loaded

        Raises:
            May log errors but never raises (graceful degradation)
        """
        all_patterns = []

        # Load from each directory
        for pattern_dir in self.pattern_dirs:
            if not pattern_dir.exists():
                logger.warning(f"[PatternLoader] Pattern directory not found: {pattern_dir}")
                continue

            for json_file in pattern_dir.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Schema validation
                    if validate_schema:
                        self._validate_schema(data, json_file)

                    # Track file modification time for hot-reload
                    self._file_mtimes[json_file] = json_file.stat().st_mtime

                    # Add patterns with source tracking
                    for pattern in data.get("patterns", []):
                        pattern["_source"] = str(json_file)
                        all_patterns.append(pattern)

                    logger.info(f"[PatternLoader] Loaded {len(data.get('patterns', []))} patterns from {json_file.name}")

                except json.JSONDecodeError as e:
                    logger.error(f"[PatternLoader] Invalid JSON in {json_file}: {e}")
                except Exception as e:
                    logger.error(f"[PatternLoader] Error loading {json_file}: {e}")

        # Sort by priority (descending - higher priority first)
        all_patterns.sort(key=lambda p: p.get("priority", 50), reverse=True)

        # Compile regex patterns
        self.patterns = all_patterns
        self.compiled_patterns = []

        for pattern in all_patterns:
            try:
                compiled = re.compile(pattern["regex"])
                self.compiled_patterns.append((
                    compiled,
                    pattern["error_key"],
                    pattern.get("has_groups", False),
                    pattern.get("priority", 50)
                ))
            except re.error as e:
                logger.error(f"[PatternLoader] Invalid regex in pattern '{pattern.get('id', 'unknown')}': {e}")

        logger.info(f"[PatternLoader] Total patterns loaded: {len(self.compiled_patterns)}")
        return len(self.compiled_patterns)

    def _validate_schema(self, data: dict, filepath: Path):
        """
        Validate JSON against schema.

        Args:
            data: Parsed JSON data
            filepath: Path to JSON file (for error messages)

        Raises:
            ValueError: If validation fails
        """
        # Check required top-level fields
        if "version" not in data:
            raise ValueError(f"Missing 'version' in {filepath}")
        if "patterns" not in data:
            raise ValueError(f"Missing 'patterns' in {filepath}")

        # Validate each pattern
        seen_ids = set()
        for i, pattern in enumerate(data["patterns"]):
            # Required fields
            required = {"id", "regex", "error_key", "priority", "category"}
            missing = required - set(pattern.keys())
            if missing:
                raise ValueError(f"Pattern #{i} in {filepath} missing fields: {missing}")

            # Unique IDs
            pattern_id = pattern["id"]
            if pattern_id in seen_ids:
                raise ValueError(f"Duplicate pattern ID '{pattern_id}' in {filepath}")
            seen_ids.add(pattern_id)

            # Valid priority range
            priority = pattern["priority"]
            if not (0 <= priority <= 100):
                raise ValueError(f"Pattern '{pattern_id}' priority {priority} out of range [0, 100]")

            # Valid category
            valid_categories = {
                "memory", "model_loading", "custom_nodes",
                "framework", "workflow", "data_type", "generic"
            }
            if pattern["category"] not in valid_categories:
                raise ValueError(f"Pattern '{pattern_id}' has invalid category '{pattern['category']}'")

    def reload_if_changed(self) -> bool:
        """
        Check if any pattern files have been modified and reload if needed.

        Returns:
            True if patterns were reloaded, False otherwise
        """
        changed = False

        for pattern_dir in self.pattern_dirs:
            if not pattern_dir.exists():
                continue

            for json_file in pattern_dir.glob("*.json"):
                try:
                    current_mtime = json_file.stat().st_mtime
                    if json_file not in self._file_mtimes or current_mtime > self._file_mtimes[json_file]:
                        changed = True
                        break
                except Exception as e:
                    logger.warning(f"[PatternLoader] Error checking {json_file}: {e}")

        if changed:
            logger.info("[PatternLoader] Pattern files changed, reloading...")
            self.load()
            return True

        return False

    def match(self, traceback_text: str) -> Optional[Tuple[str, Tuple]]:
        """
        Match traceback against patterns.

        Args:
            traceback_text: Error traceback string

        Returns:
            Tuple of (error_key, captured_groups) or None if no match
        """
        for compiled, error_key, has_groups, _ in self.compiled_patterns:
            match = compiled.search(traceback_text)
            if match:
                if has_groups:
                    return (error_key, match.groups())
                else:
                    return (error_key, ())
        return None
    
    def get_pattern_info(self, pattern_id: str) -> Optional[Dict]:
        """
        Get full pattern metadata for a given pattern ID.
        
        Args:
            pattern_id: The pattern ID (error_key) to look up
        
        Returns:
            Dictionary with pattern metadata (id, category, priority, regex, etc.),
            or None if pattern not found
        """
        for pattern in self.patterns:
            if pattern.get("error_key") == pattern_id or pattern.get("id") == pattern_id:
                return pattern
        return None

    def get_stats(self) -> Dict:
        """
        Get pattern statistics.

        Returns:
            Dictionary with pattern statistics:
            {
                "total": int,
                "by_category": {"memory": 5, ...},
                "by_priority": {"high": 15, "medium": 20, ...},
                "sources": ["builtin.json", ...]
            }
        """
        by_category = {}
        by_priority = {"high": 0, "medium": 0, "low": 0}
        sources = set()

        for pattern in self.patterns:
            # Category count
            category = pattern.get("category", "generic")
            by_category[category] = by_category.get(category, 0) + 1

            # Priority buckets
            priority = pattern.get("priority", 50)
            if priority >= 80:
                by_priority["high"] += 1
            elif priority >= 50:
                by_priority["medium"] += 1
            else:
                by_priority["low"] += 1

            # Source files
            if "_source" in pattern:
                sources.add(Path(pattern["_source"]).name)

        return {
            "total": len(self.patterns),
            "by_category": by_category,
            "by_priority": by_priority,
            "sources": sorted(sources)
        }


# ==============================================================================
# Global Instance Management
# ==============================================================================

_pattern_loader: Optional[PatternLoader] = None


def get_pattern_loader() -> PatternLoader:
    """
    Get global PatternLoader instance (singleton pattern).

    Returns:
        PatternLoader instance

    Note:
        Automatically initializes with default pattern directories on first call.
    """
    global _pattern_loader

    if _pattern_loader is None:
        # Initialize with default pattern directories
        base_dir = os.path.dirname(os.path.abspath(__file__))
        pattern_dirs = [
            os.path.join(base_dir, "patterns", "builtin"),
            os.path.join(base_dir, "patterns", "community"),
            os.path.join(base_dir, "patterns", "custom")
        ]

        _pattern_loader = PatternLoader(pattern_dirs)

        try:
            count = _pattern_loader.load()
            logger.info(f"[PatternLoader] Initialized with {count} patterns")
        except Exception as e:
            logger.error(f"[PatternLoader] Initialization failed: {e}")
            # Return instance anyway - caller will use fallback

    return _pattern_loader


def reset_pattern_loader():
    """
    Reset global PatternLoader instance.

    Useful for testing or forcing reload of all patterns.
    """
    global _pattern_loader
    _pattern_loader = None

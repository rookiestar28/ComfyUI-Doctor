import pytest
from pipeline.plugins import discover_plugins
from pathlib import Path
from config import CONFIG

def test_plugin_discovery_and_execution():
    """Verify that plugins are discovered and can be executed."""
    # Point to the community plugins directory
    plugin_dir = Path("pipeline/plugins/community").absolute()
    
    # Discover plugins
    original_enabled = CONFIG.enable_community_plugins
    original_allowlist = list(CONFIG.plugin_allowlist)
    try:
        CONFIG.enable_community_plugins = True
        CONFIG.plugin_allowlist = ["community.example"]
        plugins = discover_plugins(plugin_dir)
    finally:
        CONFIG.enable_community_plugins = original_enabled
        CONFIG.plugin_allowlist = original_allowlist
    
    # Should find at least the example plugin
    assert len(plugins) >= 1
    
    # Execute the example plugin
    # The example plugin matches "ValueError: Example Error for Plugin"
    traceback = "Something happened.\nValueError: Example Error for Plugin\nEnd."
    
    matched = False
    for matcher in plugins:
        result = matcher(traceback)
        if result:
            suggestion, metadata = result
            assert "community plugin" in suggestion
            assert metadata["matched_pattern_id"] == "EXAMPLE_PLUGIN_ERROR"
            matched = True
            break
            
    assert matched is True, "Example plugin did not match the test traceback"

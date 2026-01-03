"""
Pytest configuration for ComfyUI-Doctor tests
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def pytest_ignore_collect(collection_path, config):
    """
    Ignore __init__.py in project root (it's a ComfyUI extension with relative imports)
    """
    if collection_path.name == "__init__.py" and collection_path.parent == project_root:
        return True
    return False


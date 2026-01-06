import importlib
import importlib.util
import logging
from pathlib import Path
from typing import List, Callable, Any

logger = logging.getLogger(__name__)

def discover_plugins(plugin_dir: Path) -> List[Callable]:
    """
    Scan a directory for Python plugins and extract their matcher registration functions.
    
    Args:
        plugin_dir: Directory to scan for .py files.
        
    Returns:
        List of register_matchers functions from valid plugins.
    """
    plugins = []
    
    if not plugin_dir.exists():
        logger.debug(f"Plugin directory {plugin_dir} does not exist, skipping.")
        return plugins
        
    for py_file in plugin_dir.glob("*.py"):
        # Skip private/init files
        if py_file.name.startswith("_"): 
            continue
            
        try:
            # Dynamic import using importlib
            module_name = f"comfyui_doctor_plugin_{py_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Check for standard entry point function 'register_matchers'
                if hasattr(module, "register_matchers") and callable(module.register_matchers):
                    plugins.append(module.register_matchers)
                    logger.info(f"Loaded plugin: {py_file.name}")
                else:
                    logger.debug(f"Skipping {py_file.name}: No 'register_matchers' function found.")
        except Exception as e:
            logger.warning(f"Failed to load plugin {py_file}: {e}", exc_info=True)
            
    return plugins

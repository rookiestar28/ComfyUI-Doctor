import sys
import os
from unittest.mock import MagicMock

# Mock server
mock_server = MagicMock()
mock_routes = MagicMock()
mock_server.PromptServer.instance.routes = mock_routes
sys.modules["server"] = mock_server

# Mock aiohttp and other deps that might cause side effects or are missing
sys.modules["aiohttp"] = MagicMock()
sys.modules["folder_paths"] = MagicMock()
sys.modules["nodes"] = MagicMock()

# Import __init__
try:
    import __init__ as doctor
    print("Import successful")
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Execution failed: {e}")
    # Continue to check routes anyway if possible? No, if execution failed, routes might not be registered.
    # But let's print what we have.
    pass

# Check routes
registered = []
# mock_routes.get returns a decorator. The decorator is called.
# But we are checking if mock_routes.get was CALLED with the path.
for call in mock_routes.get.mock_calls:
    # call objects verify args
    if call.args:
        registered.append(f"GET {call.args[0]}")

for call in mock_routes.post.mock_calls:
    if call.args:
        registered.append(f"POST {call.args[0]}")

expected = [
    "GET /doctor/jobs/{job_id}",
    "POST /doctor/jobs/{job_id}/resume",
    "POST /doctor/jobs/{job_id}/cancel",
    "GET /doctor/providers/{provider_id}/status"
]

missing = []
for exp in expected:
    if exp not in registered:
        missing.append(exp)

if missing:
    print(f"FAILURE: Missing routes: {missing}")
    print(f"Found: {registered}")
    sys.exit(1)

print("SUCCESS: All routes verified.")

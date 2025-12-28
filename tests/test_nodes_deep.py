
import os
import sys
import unittest
from unittest.mock import MagicMock

# --- MOCKING DEPENDENCIES FOR TESTING NODES.PY ---
# 1. Mock torch with real capability to carry attributes
class MockTensor:
    def __init__(self, shape, dtype="float32", device="cpu", has_nan=False, has_inf=False, requires_grad=False):
        self.shape = shape
        self.dtype = dtype
        self.device = device
        self.is_meta = False
        self.requires_grad = requires_grad
        self._has_nan = has_nan
        self._has_inf = has_inf

    def numel(self):
        return self.shape[0] * self.shape[1] if hasattr(self.shape, '__getitem__') else 1

    def min(self): return MagicMock(item=lambda: -1.0)
    def max(self): return MagicMock(item=lambda: 1.0)
    def mean(self): return MagicMock(item=lambda: 0.0)
    def flatten(self): return self
    def __getitem__(self, idx): return self

# torch.isnan mock
def mock_isnan(tensor):
    m = MagicMock()
    m.any().item.return_value = tensor._has_nan
    return m

def mock_isinf(tensor):
    m = MagicMock()
    m.any().item.return_value = tensor._has_inf
    return m

mock_torch = MagicMock()
mock_torch.Tensor = MockTensor
mock_torch.isnan = mock_isnan
mock_torch.isinf = mock_isinf
sys.modules['torch'] = mock_torch

# --- PROJECT SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
module_root = os.path.abspath(os.path.join(current_dir, "..")) # ComfyUI_Runtime_Diagnostics
sys.path.append(module_root)

try:
    from nodes import DebugPrintNode
except ImportError:
    # If nodes imports torch as 'import torch', our mock works.
    # If it is inside package, we might need to add parent to path.
    sys.path.append(os.path.dirname(module_root)) # Add project root
    from ComfyUI_Runtime_Diagnostics.nodes import DebugPrintNode

# --- TEST CASE ---
print("\n>>> TEST: Deep Inspection Node <<<")

node = DebugPrintNode()

print("\n--- Test 1: Critical NaN Detection ---")
bad_tensor = MockTensor(shape=(1, 4096), has_nan=True)
node.debug_print(bad_tensor, "NAN_TEST")

print("\n--- Test 2: CONDITIONING Structure ---")
# Conditioning: [[Tensor, {dict}]]
cond_tensor = MockTensor(shape=(1, 77, 768))
conditioning = [[cond_tensor, {"pooling": "mean"}]]
node.debug_print(conditioning, "COND_TEST")

print("\n--- Test 3: Model Object ---")
class MockModel:
    def __init__(self):
        self.model_type = "SDXL"
        self.load_device = "cpu"
        self.current_device = "cuda:0"
        self.model_config = {}

model = MockModel()
node.debug_print(model, "MODEL_TEST")

print("\n>>> TEST COMPLETE")

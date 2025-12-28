
import torch
import math

class AnyType(str):
    """A special type that compares equal to any other type. 
    This allows the node to connect to any input/output without validation errors."""
    def __ne__(self, __value: object) -> bool:
        return False
    def __eq__(self, __value: object) -> bool:
        return True

# Create a universal type instance
ANY_TYPE = AnyType("*")

class DebugPrintNode:
    """
    A node that prints detailed information about the input data to the console 
    (which is captured by the logger). Acts as a pass-through with Deep Inspection.
    """
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "data": (ANY_TYPE,), # Universal input
                "prefix": ("STRING", {"default": "DEBUG"}),
            },
        }

    RETURN_TYPES = (ANY_TYPE,)
    RETURN_NAMES = ("data",)
    FUNCTION = "debug_print"
    CATEGORY = "ComfyUI-Doctor"

    def debug_print(self, data, prefix):
        print(f"\n[{prefix}] Data Inspection:")
        
        try:
            self._recursive_inspect(data, depth=0)
        except Exception as e:
            print(f"  ❌ Error inspecting data: {e}")

        return (data,)

    def _recursive_inspect(self, data, depth=0):
        indent = "  " * (depth + 1)
        
        # Max depth safety
        if depth > 3:
            print(f"{indent}Max recursion depth reached...")
            return

        # --- 1. Tensor Inspection ---
        if isinstance(data, torch.Tensor):
            self._inspect_tensor(data, indent)
            return

        # --- 2. List/Tuple (Potentially CONDITIONING or LATENT batches) ---
        if isinstance(data, (list, tuple)):
            print(f"{indent}Type: {type(data).__name__} (len={len(data)})")
            
            # Special Case: CONDITIONING is usually [[Tensor, Dict], [Tensor, Dict]...]
            if len(data) > 0 and isinstance(data[0], (list, tuple)) and len(data[0]) == 2:
                if isinstance(data[0][0], torch.Tensor) and isinstance(data[0][1], dict):
                    print(f"{indent}ℹ️ Detected Structure: CONDITIONING (Prompt + Meta)")
            
            # Inspect first and last item if long
            if len(data) > 0:
                print(f"{indent}[0]:")
                self._recursive_inspect(data[0], depth + 1)
                
            if len(data) > 1:
                print(f"{indent}... (hidden {len(data)-1} items)")
            return

        # --- 3. Dictionary (Potentially LATENT or Model Config) ---
        if isinstance(data, dict):
            print(f"{indent}Type: Dict (keys={list(data.keys())})")
            
            # Special Case: LATENT
            if "samples" in data:
                print(f"{indent}ℹ️ Detected Structure: LATENT")
                print(f"{indent}Key 'samples':")
                self._recursive_inspect(data["samples"], depth + 1)
                
                # Check for other latent keys
                for k in ["noise_mask", "batch_index"]:
                    if k in data:
                        print(f"{indent}Key '{k}': Present")

            # Generic Dict inspection (first few keys)
            else:
                for i, (k, v) in enumerate(data.items()):
                    if i >= 3:
                        print(f"{indent}... (remaining keys hidden)")
                        break
                    print(f"{indent}Key '{k}':")
                    self._recursive_inspect(v, depth + 1)
            return

        # --- 4. Objects (Model, VAE, CLIP) ---
        # Heuristic: Check for common attributes in Comfy/Torch models
        if hasattr(data, "model_config") or hasattr(data, "get_model") or hasattr(data, "encode_token_weights"):
            print(f"{indent}Type: Object ({type(data).__name__})")
            
            # Try to grab useful attributes
            if hasattr(data, "model_type"):
                print(f"{indent}Attr 'model_type': {data.model_type}")
            
            if hasattr(data, "load_device"):
                print(f"{indent}Attr 'load_device': {data.load_device}")
                
            if hasattr(data, "current_device"):
                print(f"{indent}Attr 'current_device': {data.current_device}")
                
            if hasattr(data, "dtype"):
                 print(f"{indent}Attr 'dtype': {data.dtype}")
                 
            return

        # --- Base Case: Primitives ---
        print(f"{indent}Value: {str(data)[:200]}")


    def _inspect_tensor(self, data, indent):
        print(f"{indent}Type: Tensor")
        print(f"{indent}Shape: {data.shape}")
        print(f"{indent}Dtype: {data.dtype}")
        print(f"{indent}Device: {data.device}")
        
        # Critical Checks
        if data.is_meta:
            print(f"{indent}⚠️ Meta Tensor (No data)")
            return
            
        if hasattr(data, "requires_grad") and data.requires_grad:
            print(f"{indent}⚠️ WARNING: requires_grad=True (Might waste VRAM/Time if not training)")

        # Stats
        if data.numel() > 0:
            # Check for NaN/Inf (torch.isnan/isinf work on GPU)
            has_nan = torch.isnan(data).any().item()
            has_inf = torch.isinf(data).any().item()
            
            if has_nan:
                print(f"{indent}❌ CRITICAL: Tensor contains NaN (Not a Number)!")
            if has_inf:
                print(f"{indent}❌ CRITICAL: Tensor contains Inf (Infinity)!")
                
            if not has_nan and not has_inf:
                # Only calc stats if safe
                try:
                    # P3 optimization: use view + contiguous to avoid full copy
                    numel = data.numel()
                    if numel > 100000:
                        # Use first 10k elements via view (no copy until .contiguous())
                        sample = data.view(-1)[:10000].contiguous()
                        sample_label = "First 10k"
                    else:
                        sample = data.view(-1)
                        sample_label = "All"
                         
                    d_min = sample.min().item()
                    d_max = sample.max().item()
                    d_mean = sample.float().mean().item()  # Cast to float for mean
                    print(f"{indent}Stats ({sample_label}): Min={d_min:.4f}, Max={d_max:.4f}, Mean={d_mean:.4f}")
                except Exception:
                    print(f"{indent}Stats: Could not calculate (Error)")

# Node Registration
NODE_CLASS_MAPPINGS = {
    "DebugPrintNode": DebugPrintNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DebugPrintNode": "Smart Debug Node"
}

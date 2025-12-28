"""
ComfyUI Doctor - Main Entry Point

This module initializes the smart debugging system on ComfyUI startup.
Features:
- Automatic log capture from startup
- System environment snapshot
- Error analysis with suggestions
- API endpoint for frontend integration
"""

import sys
import os
import glob
import datetime
import platform
import json
from .logger import SmartLogger, get_last_analysis, get_analysis_history
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .i18n import set_language, get_language, SUPPORTED_LANGUAGES
from .config import CONFIG

# --- LLM Environment Variable Fallbacks ---
# These can be set in system environment to provide default values
DOCTOR_LLM_API_KEY = os.getenv("DOCTOR_LLM_API_KEY")
DOCTOR_LLM_BASE_URL = os.getenv("DOCTOR_LLM_BASE_URL", "https://api.openai.com/v1")
DOCTOR_LLM_MODEL = os.getenv("DOCTOR_LLM_MODEL", "gpt-4o")


def is_local_llm_url(base_url: str) -> bool:
    """
    Check if the base URL is a local LLM service (LMStudio, Ollama, etc.)
    These typically don't require an API key.
    """
    if not base_url:
        return False
    
    base_url_lower = base_url.lower()
    local_patterns = [
        # LMStudio patterns
        "localhost:1234", "127.0.0.1:1234", "0.0.0.0:1234",
        # Ollama patterns
        "localhost:11434", "127.0.0.1:11434", "0.0.0.0:11434",
        # Generic local patterns
        "localhost/v1", "127.0.0.1/v1",
    ]
    return any(pattern in base_url_lower for pattern in local_patterns)

# --- 1. Setup Log Directory (Local to Node) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(current_dir, "logs")

if not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError as e:
        print(f"[ComfyUI-Doctor] Warning: Could not create log directory: {e}")


# --- 2. Log File Cleanup ---
def cleanup_old_logs(log_directory: str, max_files: int = 10) -> None:
    """
    Keep only the most recent N log files, delete older ones.
    
    Args:
        log_directory: Path to the logs directory.
        max_files: Maximum number of log files to keep.
    """
    try:
        log_files = sorted(glob.glob(os.path.join(log_directory, "comfyui_debug_*.log")))
        if len(log_files) > max_files:
            for old_file in log_files[:-max_files]:
                try:
                    os.remove(old_file)
                except OSError:
                    pass  # File may be locked, continue with others
    except OSError:
        pass  # Directory access may fail, silently continue


cleanup_old_logs(log_dir, CONFIG.max_log_files)


# --- 3. Check if Prestartup Logger is already installed ---
prestartup_log_path = os.environ.get("COMFYUI_DOCTOR_LOG_PATH")

if prestartup_log_path and os.path.exists(prestartup_log_path):
    # Prestartup logger was installed - use the same log file
    log_path = prestartup_log_path
    print(f"\n[ComfyUI-Doctor] 🟢 Upgrading from Prestartup Logger...")
    print(f"[ComfyUI-Doctor] 📄 Using existing log: {log_path}")
else:
    # No prestartup logger - generate new log filename
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"comfyui_debug_{timestamp}.log"
    log_path = os.path.join(log_dir, log_filename)
    print(f"\n[ComfyUI-Doctor] 🟢 Initializing Smart Debugger...")
    print(f"[ComfyUI-Doctor] 📄 Log file: {log_path}")


# --- 4. Install/Upgrade to Full Smart Logger ---
# This will replace the minimal PrestartupLogger with the full-featured SmartLogger
SmartLogger.install(log_path)


# --- 5. Log System Information (Hardware Snapshot) ---
def log_system_info() -> None:
    """Log system and hardware information at startup."""
    print(f"\n{'='*20} SYSTEM SNAPSHOT {'='*20}")
    print(f"OS: {platform.system()} {platform.release()} ({platform.version()})")
    print(f"Python: {sys.version.split()[0]}")
    
    try:
        import torch
        print(f"PyTorch: {torch.__version__}")
        print(f"CUDA Available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"CUDA Version: {torch.version.cuda}")
            device_count = torch.cuda.device_count()
            print(f"GPU Count: {device_count}")
            for i in range(device_count):
                props = torch.cuda.get_device_properties(i)
                print(f"  GPU {i}: {props.name} (VRAM: {props.total_memory / 1024**3:.2f} GB)")
    except ImportError:
        print("PyTorch: Not Installed (or not found in this env)")
    
    # Log ComfyUI Arguments if available
    print(f"Args: {sys.argv}")
    print(f"{'='*57}\n")

log_system_info()


# --- 6. API Registration ---
try:
    import server
    import aiohttp
    from aiohttp import web

    @server.PromptServer.instance.routes.get("/debugger/last_analysis")
    async def api_get_last_analysis(request):
        """
        API endpoint to get the last error analysis.
        
        Returns:
            JSON with status, log_path, last error details, and suggestion.
        """
        analysis = get_last_analysis()
        return web.json_response({
            "status": "running",
            "log_path": log_path,
            "language": get_language(),
            "supported_languages": SUPPORTED_LANGUAGES,
            "last_error": analysis.get("error"),
            "suggestion": analysis.get("suggestion"),
            "timestamp": analysis.get("timestamp"),
            "node_context": analysis.get("node_context"),
        })
    
    @server.PromptServer.instance.routes.post("/debugger/set_language")
    async def api_set_language(request):
        """
        API endpoint to change the suggestion language.
        
        Body: {"language": "zh_TW"}
        """
        try:
            data = await request.json()
            if "language" in data:
                set_language(data["language"])
                return web.json_response({"success": True, "language": data["language"]})
            return web.json_response({"success": False, "message": "Missing language parameter"}, status=400)
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    @server.PromptServer.instance.routes.post("/doctor/analyze")
    async def api_analyze_error(request):
        """
        API endpoint to analyze error with LLM.
        Payload: { "error": str, "node_context": dict, "api_key": str, "base_url": str, "model": str, "language": str }
        
        Security: API key is transmitted but never logged or persisted.
        """
        try:
            data = await request.json()
            error_text = data.get("error")
            node_context = data.get("node_context", {})
            api_key = data.get("api_key")
            base_url = data.get("base_url", "https://api.openai.com/v1")
            model = data.get("model", "gpt-4o")
            language = data.get("language", "en")

            # Validate required parameters
            # Check if this is a local LLM (doesn't require API key)
            is_local = is_local_llm_url(base_url)
            
            # Only require API key for non-local LLMs
            if not api_key and not is_local:
                return web.json_response({"error": "Missing API Key"}, status=401)

            if not error_text:
                return web.json_response({"error": "No error text provided"}, status=400)

            # Truncate error text to prevent token overflow (roughly 8000 chars ≈ 2000 tokens)
            MAX_ERROR_LENGTH = 8000
            if len(error_text) > MAX_ERROR_LENGTH:
                error_text = error_text[:MAX_ERROR_LENGTH] + "\n\n[... truncated ...]"

            # Construct Prompt - Enhanced for ComfyUI debugging
            system_prompt = (
                "You are an expert ComfyUI debugger and Python specialist. "
                "ComfyUI is a node-based Stable Diffusion workflow editor where users connect nodes "
                "(e.g., 'KSampler', 'VAEDecode', 'CheckpointLoaderSimple', 'CLIPTextEncode') to build image generation pipelines.\n\n"
                "Common ComfyUI error categories:\n"
                "- **OOM (Out of Memory)**: Reduce batch_size, lower resolution, use --lowvram or --cpu flags\n"
                "- **Missing Models**: Check if model file exists in ComfyUI/models/ folder, verify filename spelling\n"
                "- **Type Mismatch**: Ensure connected nodes have compatible data types (MODEL, CLIP, VAE, LATENT, IMAGE)\n"
                "- **CUDA/cuDNN Errors**: Often driver version issues, try updating GPU drivers or PyTorch\n"
                "- **Shape Mismatch**: Usually caused by incompatible image sizes or LoRA/model combinations\n"
                "- **Module Not Found**: Missing Python dependencies, run 'pip install <module>' in ComfyUI environment\n\n"
                "Analyze the error and provide:\n"
                "1. **Root Cause** (1-2 sentences, be specific)\n"
                "2. **Solution Steps** (numbered list, actionable commands if applicable)\n"
                "3. **Prevention Tips** (optional, if the error is common)\n\n"
                f"Respond in {language}. Be concise but thorough."
            )
            
            user_prompt = f"Error:\n{error_text}\n\n"
            if node_context:
                user_prompt += f"Node Context: {json.dumps(node_context, indent=2)}\n"
            
            # Prepare headers (API key is NOT logged)
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Normalize Base URL
            base_url = base_url.rstrip("/")
            # Auto-append /v1 if missing and looks like a standard provider
            if not base_url.endswith("/v1") and any(p in base_url for p in ["openai.com", "deepseek.com"]):
                base_url += "/v1"
            
            url = f"{base_url}/chat/completions"
            
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.5
            }

            # Set timeout to prevent hanging requests
            timeout = aiohttp.ClientTimeout(total=60)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_msg = await response.text()
                        # Truncate error message for readability
                        if len(error_msg) > 500:
                            error_msg = error_msg[:500] + "..."
                        return web.json_response(
                            {"error": f"LLM Provider Error ({response.status}): {error_msg}"}, 
                            status=response.status
                        )
                    
                    # Safely parse JSON response
                    try:
                        result = await response.json()
                        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                        if not content:
                            return web.json_response({"error": "Empty response from LLM"}, status=502)
                        return web.json_response({"analysis": content})
                    except (json.JSONDecodeError, KeyError, IndexError) as parse_err:
                        return web.json_response(
                            {"error": f"Failed to parse LLM response: {str(parse_err)}"}, 
                            status=502
                        )

        except aiohttp.ClientError as e:
            # Network-level errors (timeout, connection refused, etc.)
            print(f"[ComfyUI-Doctor] LLM Network Error: {e}")
            return web.json_response({"error": f"Network Error: {str(e)}"}, status=503)
        except Exception as e:
            print(f"[ComfyUI-Doctor] LLM Analysis Failed: {e}")
            return web.json_response({"error": str(e)}, status=500)
        
    @server.PromptServer.instance.routes.get("/debugger/history")
    async def api_get_history(request):
        """
        API endpoint to get error analysis history.
        
        Returns:
            JSON with history list (most recent first).
        """
        return web.json_response({
            "history": get_analysis_history(),
            "count": len(get_analysis_history()),
        })

    @server.PromptServer.instance.routes.post("/doctor/verify_key")
    async def api_verify_key(request):
        """
        API endpoint to verify LLM API key validity.
        Tests by calling the /models endpoint.
        
        Payload: { "base_url": str, "api_key": str }
        Returns: { "success": bool, "message": str, "is_local": bool }
        """
        try:
            data = await request.json()
            base_url = data.get("base_url", DOCTOR_LLM_BASE_URL)
            api_key = data.get("api_key", "")
            
            # Check if this is a local LLM
            is_local = is_local_llm_url(base_url)
            
            # Local LLMs may not require API key
            if not api_key and not is_local:
                return web.json_response({
                    "success": False,
                    "message": "No API key provided",
                    "is_local": False
                })
            
            # Normalize base URL
            base_url = base_url.rstrip("/")
            
            # Use placeholder for local LLMs without key
            if is_local and not api_key:
                api_key = "local-llm"
            
            # Prepare request
            headers = {"Authorization": f"Bearer {api_key}"}
            url = f"{base_url}/models"
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        msg = "API key is valid" if not is_local else "Local LLM connection successful"
                        return web.json_response({
                            "success": True,
                            "message": msg,
                            "is_local": is_local
                        })
                    else:
                        error_text = await response.text()
                        if len(error_text) > 200:
                            error_text = error_text[:200] + "..."
                        return web.json_response({
                            "success": False,
                            "message": f"Verification failed ({response.status}): {error_text}",
                            "is_local": is_local
                        })
                        
        except aiohttp.ClientError as e:
            return web.json_response({
                "success": False,
                "message": f"Connection error: {str(e)}",
                "is_local": is_local_llm_url(data.get("base_url", "")) if 'data' in locals() else False
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "message": f"Error: {str(e)}",
                "is_local": False
            })

    @server.PromptServer.instance.routes.post("/doctor/list_models")
    async def api_list_models(request):
        """
        API endpoint to list available LLM models.
        
        Payload: { "base_url": str, "api_key": str }
        Returns: { "success": bool, "models": list[{name, id}], "message": str }
        """
        try:
            data = await request.json()
            base_url = data.get("base_url", DOCTOR_LLM_BASE_URL)
            api_key = data.get("api_key", "")
            
            is_local = is_local_llm_url(base_url)
            
            if not api_key and not is_local:
                return web.json_response({
                    "success": False,
                    "models": [],
                    "message": "No API key provided"
                })
            
            base_url = base_url.rstrip("/")
            if is_local and not api_key:
                api_key = "local-llm"
            
            headers = {"Authorization": f"Bearer {api_key}"}
            url = f"{base_url}/models"
            
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        return web.json_response({
                            "success": False,
                            "models": [],
                            "message": f"Failed to fetch models ({response.status})"
                        })
                    
                    try:
                        result = await response.json()
                        models = []
                        
                        # Handle OpenAI-style response
                        if "data" in result:
                            for m in result["data"]:
                                model_id = m.get("id", "")
                                models.append({
                                    "id": model_id,
                                    "name": model_id
                                })
                        # Handle Ollama-style response
                        elif "models" in result:
                            for m in result["models"]:
                                model_name = m.get("name", m.get("model", ""))
                                models.append({
                                    "id": model_name,
                                    "name": model_name
                                })
                        
                        return web.json_response({
                            "success": True,
                            "models": models,
                            "message": f"Found {len(models)} models"
                        })
                        
                    except (json.JSONDecodeError, KeyError) as e:
                        return web.json_response({
                            "success": False,
                            "models": [],
                            "message": f"Failed to parse model list: {str(e)}"
                        })
                        
        except aiohttp.ClientError as e:
            return web.json_response({
                "success": False,
                "models": [],
                "message": f"Connection error: {str(e)}"
            })
        except Exception as e:
            return web.json_response({
                "success": False,
                "models": [],
                "message": f"Error: {str(e)}"
            })
        
    print("[ComfyUI-Doctor] 🌐 API Hooks registered:")
    print("  - GET  /debugger/last_analysis")
    print("  - GET  /debugger/history")
    print("  - POST /debugger/set_language")
    print("  - POST /doctor/analyze")
    print("  - POST /doctor/verify_key")
    print("  - POST /doctor/list_models")

except ImportError:
    print("[ComfyUI-Doctor] ⚠️ Server module not found (Running in standalone mode?)")
except Exception as e:
    print(f"[ComfyUI-Doctor] ⚠️ Failed to register API: {e}")


# Web directory for frontend assets (required by ComfyUI)
WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

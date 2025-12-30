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
import logging
from logging.handlers import RotatingFileHandler
from .logger import SmartLogger, get_last_analysis, get_analysis_history, clear_analysis_history
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .i18n import set_language, get_language, SUPPORTED_LANGUAGES
from .config import CONFIG
from .session_manager import SessionManager

# --- LLM Environment Variable Fallbacks ---
# These can be set in system environment to provide default values
DOCTOR_LLM_API_KEY = os.getenv("DOCTOR_LLM_API_KEY")
DOCTOR_LLM_BASE_URL = os.getenv("DOCTOR_LLM_BASE_URL", "https://api.openai.com/v1")
DOCTOR_LLM_MODEL = os.getenv("DOCTOR_LLM_MODEL", "gpt-4o")

# --- Local LLM Service URLs (Environment Variable Support) ---
# Allows cross-platform compatibility (Windows vs WSL2, Docker, etc.)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")


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


def validate_ssrf_url(base_url: str, allow_local_llm: bool = True) -> tuple[bool, str]:
    """
    S2: Validate base URL to prevent SSRF attacks.
    
    Blocks:
    - Private IP ranges (10.x, 172.16-31.x, 192.168.x)
    - Localhost (127.x.x.x, localhost, ::1)
    - Link-local addresses (169.254.x.x)
    - Non-HTTP protocols (file://, ftp://, etc.)
    - Metadata endpoints (169.254.169.254)
    
    Args:
        base_url: The URL to validate
        allow_local_llm: If True, allows known local LLM patterns (LMStudio, Ollama)
        
    Returns:
        (is_valid, error_message) tuple
    """
    import ipaddress
    from urllib.parse import urlparse
    
    if not base_url:
        return False, "Empty URL"
    
    # Allow known local LLM patterns if enabled
    if allow_local_llm and is_local_llm_url(base_url):
        return True, ""
    
    try:
        parsed = urlparse(base_url)
    except Exception as e:
        return False, f"Invalid URL format: {e}"
    
    # Check protocol
    if parsed.scheme not in ('http', 'https'):
        return False, f"Invalid protocol: {parsed.scheme}. Only HTTP/HTTPS allowed."
    
    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname"
    
    hostname_lower = hostname.lower()
    
    # Block localhost patterns
    localhost_patterns = ['localhost', '127.0.0.1', '::1', '0.0.0.0']
    if hostname_lower in localhost_patterns:
        return False, f"Blocked: localhost access ({hostname})"
    
    # Check if hostname is an IP address
    try:
        ip = ipaddress.ip_address(hostname)
        
        # Block loopback
        if ip.is_loopback:
            return False, f"Blocked: loopback address ({hostname})"
        
        # Block private IPs
        if ip.is_private:
            return False, f"Blocked: private IP address ({hostname})"
        
        # Block link-local
        if ip.is_link_local:
            return False, f"Blocked: link-local address ({hostname})"
        
        # Block reserved IPs (includes metadata endpoints like 169.254.169.254)
        if ip.is_reserved:
            return False, f"Blocked: reserved IP address ({hostname})"
        
        # Block multicast
        if ip.is_multicast:
            return False, f"Blocked: multicast address ({hostname})"
            
    except ValueError:
        # Not an IP address, it's a hostname - check for suspicious patterns
        # Block .local domains
        if hostname_lower.endswith('.local'):
            return False, f"Blocked: .local domain ({hostname})"
        
        # Block internal TLDs sometimes used in corporate networks
        internal_tlds = ['.internal', '.corp', '.lan', '.home', '.localdomain']
        for tld in internal_tlds:
            if hostname_lower.endswith(tld):
                return False, f"Blocked: internal domain ({hostname})"
    
    return True, ""

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


# --- 5. Setup API Logger for Doctor Operations ---
def setup_api_logger():
    """
    Create a dedicated logger for API operations.
    Logs to logs/api_operations.log (separate from SmartLogger's error logs).
    """
    api_logger = logging.getLogger('ComfyUI-Doctor-API')

    # Prevent duplicate handlers if called multiple times
    if api_logger.handlers:
        return api_logger

    api_logger.setLevel(logging.INFO)

    # File handler with rotation (max 5MB, keep 3 backups)
    api_log_path = os.path.join(log_dir, 'api_operations.log')
    file_handler = RotatingFileHandler(
        api_log_path,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )

    # Formatter with timestamp and level
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    api_logger.addHandler(file_handler)

    # Console handler for terminal output (user requested visibility)
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        '[Doctor-API] [%(levelname)s] %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    api_logger.addHandler(console_handler)

    # Prevent propagation to root logger (avoid duplicate console output)
    api_logger.propagate = False

    return api_logger

# Initialize logger
logger = setup_api_logger()
print(f"[ComfyUI-Doctor] 📋 API logger initialized: {os.path.join(log_dir, 'api_operations.log')}")


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
            workflow = data.get("workflow")  # F3: Workflow context from frontend
            api_key = data.get("api_key")
            base_url = data.get("base_url", "https://api.openai.com/v1")
            model = data.get("model", "gpt-4o")
            language = data.get("language", "en")

            logger.info(f"Analyze API called - error_length={len(error_text) if error_text else 0}, has_workflow={bool(workflow)}, model={model}")

            # S2: SSRF protection - validate base URL
            is_valid, ssrf_error = validate_ssrf_url(base_url)
            if not is_valid:
                logger.warning(f"SSRF blocked: {ssrf_error}")
                return web.json_response({"error": f"Invalid Base URL: {ssrf_error}"}, status=400)

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
            
            # R8: Smart workflow truncation (preserves error-related nodes)
            if workflow:
                from .truncate_workflow import truncate_workflow_smart
                error_node_id = node_context.get("id") if node_context else None
                workflow, truncation_meta = truncate_workflow_smart(workflow, error_node_id, max_chars=4000)
                if truncation_meta.get("truncation_method") != "none":
                    logger.info(f"Workflow truncated: {truncation_meta}")

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
                user_prompt += f"Node Context: {json.dumps(node_context, indent=2)}\n\n"
            
            # F3: Include workflow context if available
            if workflow:
                user_prompt += f"Workflow Structure (simplified):\n{workflow}\n"
            
            # Prepare headers (API key is NOT logged)
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Normalize Base URL
            base_url = base_url.rstrip("/")

            # Determine if this is Ollama or OpenAI-compatible API
            is_ollama = is_local_llm_url(base_url) and ("11434" in base_url or "ollama" in base_url.lower())

            if is_ollama:
                # Ollama uses /api/chat endpoint (remove /v1 if present)
                if base_url.endswith("/v1"):
                    base_url = base_url[:-3]
                url = f"{base_url}/api/chat"
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "stream": False
                }
            else:
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

            session = await SessionManager.get_session()
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
                    # Handle both Ollama and OpenAI response formats
                    if is_ollama:
                        content = result.get('message', {}).get('content', '')
                    else:
                        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    if not content:
                        return web.json_response({"error": "Empty response from LLM"}, status=502)
                    logger.info(f"Analysis successful, response length={len(content)}")
                    return web.json_response({"analysis": content})
                except (json.JSONDecodeError, KeyError, IndexError) as parse_err:
                    return web.json_response(
                        {"error": f"Failed to parse LLM response: {str(parse_err)}"}, 
                        status=502
                    )

        except aiohttp.ClientError as e:
            # Network-level errors (timeout, connection refused, etc.)
            logger.error(f"LLM Network Error: {str(e)}")
            return web.json_response({"error": f"Network Error: {str(e)}"}, status=503)
        except Exception as e:
            logger.error(f"LLM Analysis Failed: {str(e)}")
            return web.json_response({"error": str(e)}, status=500)

    @server.PromptServer.instance.routes.post("/doctor/chat")
    async def api_chat(request):
        """
        API endpoint for multi-turn chat with LLM (SSE streaming).
        
        Payload: {
            "messages": [{"role": "user|assistant", "content": "..."}],
            "error_context": {"error": "...", "node_context": {...}, "workflow": "..."},
            "api_key": str,
            "base_url": str,
            "model": str,
            "language": str,
            "stream": bool (default: true)
        }
        
        Response (SSE):
            data: {"delta": "token", "done": false}
            data: {"delta": "", "done": true}
        """
        try:
            data = await request.json()
            messages = data.get("messages", [])
            error_context = data.get("error_context", {})
            api_key = data.get("api_key", "")
            base_url = data.get("base_url", "https://api.openai.com/v1")
            model = data.get("model", "gpt-4o")
            language = data.get("language", "en")
            stream = data.get("stream", True)
            intent = data.get("intent", "chat")  # New: intent parameter
            selected_nodes = data.get("selected_nodes", [])  # New: node selection context
            
            logger.info(f"Chat API called - model={model}, intent={intent}, messages={len(messages)}, stream={stream}")
            
            # S2: SSRF protection - validate base URL
            is_valid, ssrf_error = validate_ssrf_url(base_url)
            if not is_valid:
                logger.warning(f"SSRF blocked: {ssrf_error}")
                return web.json_response({"error": f"Invalid Base URL: {ssrf_error}"}, status=400)

            # Validate
            is_local = is_local_llm_url(base_url)
            if not api_key and not is_local:
                return web.json_response({"error": "Missing API Key"}, status=401)
            
            if not messages:
                return web.json_response({"error": "No messages provided"}, status=400)
            
            # Build system prompt with error context
            error_text = error_context.get("error", "")
            node_context = error_context.get("node_context", {})
            workflow = error_context.get("workflow", "")
            
            # Truncate to prevent token overflow
            MAX_ERROR_LENGTH = 4000
            if len(error_text) > MAX_ERROR_LENGTH:
                error_text = error_text[:MAX_ERROR_LENGTH] + "\n[... truncated ...]"
            
            # R8: Smart workflow truncation
            if workflow:
                from .truncate_workflow import truncate_workflow_smart
                workflow, _ = truncate_workflow_smart(workflow, max_chars=2000)
            
            # Intent-aware system prompt
            if intent == "explain_node":
                system_prompt = (
                    "You are an expert ComfyUI node documentation assistant. ComfyUI is a node-based Stable Diffusion workflow editor.\n\n"
                    "Your task is to explain how specific nodes work, their inputs/outputs, and best practices for using them.\n"
                    "Be concise, clear, and provide practical examples when relevant.\n"
                    f"Respond in {language}.\n\n"
                )
                if selected_nodes:
                    system_prompt += f"**Selected Node(s):** {json.dumps(selected_nodes)}\n\n"
            else:
                # Default chat/debug intent
                system_prompt = (
                    "You are an expert ComfyUI debugger. ComfyUI is a node-based Stable Diffusion workflow editor.\n\n"
                    "You are helping the user debug an error. Be concise, helpful, and provide actionable solutions.\n"
                    f"Respond in {language}.\n\n"
                )
            
            if error_text:
                system_prompt += f"**Current Error:**\n```\n{error_text}\n```\n\n"
            
            if node_context:
                system_prompt += f"**Node Context:** {json.dumps(node_context)}\n\n"
            
            if workflow:
                system_prompt += f"**Workflow (simplified):** {workflow}\n\n"
            
            # Build conversation with system prompt
            api_messages = [{"role": "system", "content": system_prompt}]
            
            # Limit conversation history to prevent token overflow
            MAX_HISTORY = 10
            recent_messages = messages[-MAX_HISTORY:] if len(messages) > MAX_HISTORY else messages
            api_messages.extend(recent_messages)
            
            # Prepare request
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            base_url = base_url.rstrip("/")

            # Determine if this is Ollama or OpenAI-compatible API
            is_ollama = is_local_llm_url(base_url) and ("11434" in base_url or "ollama" in base_url.lower())

            if is_ollama:
                # Ollama uses /api/chat endpoint (remove /v1 if present)
                if base_url.endswith("/v1"):
                    base_url = base_url[:-3]
                url = f"{base_url}/api/chat"
            else:
                # OpenAI-compatible: auto-append /v1 if needed
                if not base_url.endswith("/v1") and any(p in base_url for p in ["openai.com", "deepseek.com"]):
                    base_url += "/v1"
                url = f"{base_url}/chat/completions"

            logger.info(f"Connecting to LLM: {url}")
            
            payload = {
                "model": model,
                "messages": api_messages,
                "temperature": 0.7,
                "stream": stream
            }
            
            if not stream:
                # Non-streaming fallback
                session = await SessionManager.get_session()
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_msg = await response.text()
                        logger.error(f"LLM non-stream error: {error_msg[:200]}")
                        return web.json_response({"error": f"LLM Error: {error_msg[:500]}"}, status=response.status)
                    
                    result = await response.json()
                    # Handle both Ollama and OpenAI response formats
                    if is_ollama:
                        content = result.get('message', {}).get('content', '')
                    else:
                        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                    logger.info(f"LLM response received (non-stream), length={len(content)}")
                    return web.json_response({"content": content, "done": True})

            # SSE Streaming response
            logger.info("Starting SSE stream...")
            response = web.StreamResponse(
                status=200,
                reason='OK',
                headers={
                    'Content-Type': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'X-Accel-Buffering': 'no',
                }
            )
            await response.prepare(request)
            
            try:
                session = await SessionManager.get_session()
                async with session.post(url, json=payload, headers=headers) as llm_response:
                    if llm_response.status != 200:
                        error_msg = await llm_response.text()
                        logger.error(f"LLM stream error: {error_msg[:200]}")
                        error_data = json.dumps({"error": f"LLM Error: {error_msg[:200]}", "done": True})
                        await response.write(f"data: {error_data}\n\n".encode('utf-8'))
                        return response
                    
                    # Stream chunks with newline buffering to handle partial lines
                    buffer = ""
                    stream_done = False
                    async for chunk in llm_response.content.iter_chunked(1024):
                        buffer += chunk.decode('utf-8', errors='ignore')

                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            line = line.strip()
                            if not line:
                                continue

                            # Handle different streaming formats
                            if is_ollama:
                                # Ollama uses newline-delimited JSON (not SSE)
                                try:
                                    chunk_json = json.loads(line)
                                    # Check if stream is done
                                    if chunk_json.get('done', False):
                                        done_data = json.dumps({"delta": "", "done": True})
                                        await response.write(f"data: {done_data}\n\n".encode('utf-8'))
                                        stream_done = True
                                        break
                                    # Extract content delta
                                    delta = chunk_json.get('message', {}).get('content', '')
                                    if delta:
                                        chunk_data = json.dumps({"delta": delta, "done": False})
                                        await response.write(f"data: {chunk_data}\n\n".encode('utf-8'))
                                except json.JSONDecodeError:
                                    continue
                            else:
                                # OpenAI uses SSE format
                                if not line.startswith('data:'):
                                    continue

                                payload_str = line[5:].strip()
                                if payload_str == '[DONE]':
                                    done_data = json.dumps({"delta": "", "done": True})
                                    await response.write(f"data: {done_data}\n\n".encode('utf-8'))
                                    stream_done = True
                                    break

                                if not payload_str:
                                    continue

                                try:
                                    chunk_json = json.loads(payload_str)
                                    delta = chunk_json.get('choices', [{}])[0].get('delta', {}).get('content', '')
                                    if delta:
                                        chunk_data = json.dumps({"delta": delta, "done": False})
                                        await response.write(f"data: {chunk_data}\n\n".encode('utf-8'))
                                except json.JSONDecodeError:
                                    continue

                        if stream_done:
                            break
                    
                    # Process any remaining buffered line if stream ended without newline
                    if not stream_done and buffer.strip():
                        line = buffer.strip()
                        if is_ollama:
                            # Ollama newline-delimited JSON
                            try:
                                chunk_json = json.loads(line)
                                if chunk_json.get('done', False):
                                    done_data = json.dumps({"delta": "", "done": True})
                                    await response.write(f"data: {done_data}\n\n".encode('utf-8'))
                                else:
                                    delta = chunk_json.get('message', {}).get('content', '')
                                    if delta:
                                        chunk_data = json.dumps({"delta": delta, "done": False})
                                        await response.write(f"data: {chunk_data}\n\n".encode('utf-8'))
                            except json.JSONDecodeError:
                                pass
                        else:
                            # OpenAI SSE format
                            if line.startswith('data:'):
                                payload_str = line[5:].strip()
                                if payload_str == '[DONE]':
                                    done_data = json.dumps({"delta": "", "done": True})
                                    await response.write(f"data: {done_data}\n\n".encode('utf-8'))
                                else:
                                    try:
                                        chunk_json = json.loads(payload_str)
                                        delta = chunk_json.get('choices', [{}])[0].get('delta', {}).get('content', '')
                                        if delta:
                                            chunk_data = json.dumps({"delta": delta, "done": False})
                                            await response.write(f"data: {chunk_data}\n\n".encode('utf-8'))
                                    except json.JSONDecodeError:
                                        pass
                
            except Exception as stream_err:
                error_data = json.dumps({"error": str(stream_err), "done": True})
                await response.write(f"data: {error_data}\n\n".encode('utf-8'))
            
            return response
            
        except aiohttp.ClientError as e:
            print(f"[ComfyUI-Doctor] Chat Network Error: {e}")
            return web.json_response({"error": f"Network Error: {str(e)}"}, status=503)
        except Exception as e:
            print(f"[ComfyUI-Doctor] Chat Failed: {e}")
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

    @server.PromptServer.instance.routes.post("/debugger/clear_history")
    async def api_clear_history(request):
        """
        API endpoint to clear error analysis history.
        
        Returns:
            JSON with success status.
        """
        try:
            success = clear_analysis_history()
            return web.json_response({"success": success})
        except Exception as e:
            return web.json_response({"success": False, "message": str(e)}, status=500)

    @server.PromptServer.instance.routes.get("/doctor/provider_defaults")
    async def api_get_provider_defaults(request):
        """
        API endpoint to get default URLs for LLM providers.
        Supports environment variable overrides for cross-platform compatibility.

        Returns:
            JSON with provider default URLs.
        """
        return web.json_response({
            "ollama": OLLAMA_BASE_URL,
            "lmstudio": LMSTUDIO_BASE_URL,
            "openai": "https://api.openai.com/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
            "xai": "https://api.x.ai/v1",
            "openrouter": "https://openrouter.ai/api/v1"
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
            
            # S2: SSRF protection - validate base URL
            is_valid, ssrf_error = validate_ssrf_url(base_url)
            if not is_valid:
                logger.warning(f"SSRF blocked in verify_key: {ssrf_error}")
                return web.json_response({
                    "success": False,
                    "message": f"Invalid Base URL: {ssrf_error}",
                    "is_local": False
                })

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
            
            session = await SessionManager.get_session()
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    msg = "API key is valid" if not is_local else "Local LLM connection successful"
                    logger.info(f"API key verification successful - base_url={base_url}, is_local={is_local}")
                    return web.json_response({
                        "success": True,
                        "message": msg,
                        "is_local": is_local
                    })
                else:
                    error_text = await response.text()
                    if len(error_text) > 200:
                        error_text = error_text[:200] + "..."
                    logger.warning(f"API key verification failed - status={response.status}, base_url={base_url}")
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
            
            # S2: SSRF protection - validate base URL
            is_valid, ssrf_error = validate_ssrf_url(base_url)
            if not is_valid:
                logger.warning(f"SSRF blocked in list_models: {ssrf_error}")
                return web.json_response({
                    "success": False,
                    "models": [],
                    "message": f"Invalid Base URL: {ssrf_error}"
                })

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

            # Determine if this is Ollama or OpenAI-compatible API
            is_ollama = is_local_llm_url(base_url) and ("11434" in base_url or "ollama" in base_url.lower())

            if is_ollama:
                # Ollama uses /api/tags endpoint (remove /v1 if present)
                if base_url.endswith("/v1"):
                    base_url = base_url[:-3]
                url = f"{base_url}/api/tags"
            else:
                url = f"{base_url}/models"

            headers = {"Authorization": f"Bearer {api_key}"}
            
            session = await SessionManager.get_session()
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

                    logger.info(f"Retrieved {len(models)} models from {url}")
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
    print("  - POST /debugger/clear_history")
    print("  - POST /doctor/analyze")
    print("  - POST /doctor/chat (SSE streaming)")
    print("  - POST /doctor/verify_key")
    print("  - POST /doctor/list_models")

except ImportError:
    print("[ComfyUI-Doctor] ⚠️ Server module not found (Running in standalone mode?)")
except Exception as e:
    print(f"[ComfyUI-Doctor] ⚠️ Failed to register API: {e}")


# Web directory for frontend assets (required by ComfyUI)
WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

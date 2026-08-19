"""
ComfyUI PromptServer route registration for ComfyUI-Doctor.

Route handlers live outside the package entry point so __init__.py remains a
startup/export module for the ComfyUI custom-node host.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from .services.prompt_helpers import (
    categorize_error,
    collect_error_context,
    get_error_analysis_prompt,
    parse_language_code,
    validate_fix_schema,
)
from .terminal_output import emit_doctor_log

logger = logging.getLogger("ComfyUI-Doctor-API")


def _local_llm_auth_placeholder() -> str:
    return "local-llm"


REGISTERED_ROUTE_DESCRIPTIONS = [
    "  - GET  /debugger/last_analysis",
    "  - GET  /debugger/history",
    "  - POST /debugger/set_language",
    "  - POST /debugger/clear_history",
    "  - GET  /doctor/ui_text",
    "  - POST /doctor/analyze",
    "  - POST /doctor/chat (SSE streaming)",
    "  - GET  /doctor/provider_defaults",
    "  - POST /doctor/verify_key",
    "  - POST /doctor/list_models",
    "  - GET  /doctor/secrets/status (S8)",
    "  - PUT  /doctor/secrets (S8)",
    "  - DELETE /doctor/secrets/{provider} (S8)",
    "  - GET  /doctor/statistics (F4)",
    "  - POST /doctor/statistics/reset (F4)",
    "  - POST /doctor/mark_resolved (F4)",
    "  - POST /doctor/feedback/preview (F16)",
    "  - POST /doctor/feedback/submit (F16)",
    "  - GET  /doctor/health",
    "  - GET  /doctor/plugins",
    "  - GET  /doctor/telemetry/status (S3)",
    "  - GET  /doctor/telemetry/buffer (S3)",
    "  - POST /doctor/telemetry/track (S3)",
    "  - POST /doctor/telemetry/clear (S3)",
    "  - GET  /doctor/telemetry/export (S3)",
    "  - POST /doctor/telemetry/toggle (S3)",
    "  - POST /doctor/health_check (F14)",
    "  - GET  /doctor/health_report (F14)",
    "  - GET  /doctor/health_history (F14)",
    "  - POST /doctor/health_ack (F14)",
]


def _print_registered_routes(startup_print) -> None:
    startup_print("API hooks registered:")
    for route_description in REGISTERED_ROUTE_DESCRIPTIONS:
        startup_print(route_description)
    startup_print("Questions, updates, suggestions, and contributions are welcome.")
    startup_print("GitHub: https://github.com/rookiestar28/ComfyUI-Doctor")
    startup_print("")
    startup_print("\n")


def register_api_routes(context: dict) -> None:
    """Register all PromptServer routes using dependencies from __init__.py."""
    globals().update(context)
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
            "analysis_metadata": analysis.get("analysis_metadata"),
            "matched_pattern_id": analysis.get("matched_pattern_id"),
            "pattern_category": analysis.get("pattern_category"),
            "pattern_priority": analysis.get("pattern_priority"),
            "resolution_status": analysis.get("resolution_status"),
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
            return _error_response("Missing language parameter", status=400, code="missing_language")
        except Exception as e:
            return _error_response(str(e), status=500)

    @server.PromptServer.instance.routes.get("/doctor/ui_text")
    async def api_get_ui_text(request):
        """
        API endpoint to get all UI text translations for current language.

        Query params (optional): ?lang=zh_TW
        """
        try:
            lang = request.query.get("lang", get_language())
            ui_text = UI_TEXT.get(lang, UI_TEXT["en"])

            def _get_doctor_meta() -> dict:
                # Best-effort metadata for UI display.
                # IMPORTANT: prefer pyproject.toml values for UI consistency.
                meta = {
                    "name": "ComfyUI-Doctor",
                    "version": "unknown",
                    "repository": "https://github.com/rookiestar28/ComfyUI-Doctor",
                }

                # Primary source: local pyproject.toml
                try:
                    from pathlib import Path
                    import re

                    pyproject_path = Path(__file__).resolve().parent / "pyproject.toml"
                    if pyproject_path.exists():
                        content = pyproject_path.read_text(encoding="utf-8", errors="ignore")
                        m = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', content)
                        if m:
                            meta["version"] = m.group(1).strip()
                        m_repo = re.search(
                            r'(?ms)^\[project\.urls\].*?^Repository\s*=\s*"([^"]+)"\s*$',
                            content,
                        )
                        if m_repo:
                            meta["repository"] = m_repo.group(1).strip()
                except Exception:
                    pass

                # Fallback source: installed distribution metadata.
                if meta["version"] in ("unknown", "", None):
                    try:
                        import importlib.metadata as _metadata  # py3.8+

                        # Distribution name may differ depending on install method.
                        for dist_name in ("ComfyUI-Doctor", "comfyui-doctor"):
                            try:
                                meta["version"] = _metadata.version(dist_name)
                                break
                            except Exception:
                                pass
                    except Exception:
                        pass
                return meta

            return web.json_response({
                "language": lang,
                "text": ui_text,
                "meta": _get_doctor_meta(),
            })
        except Exception as e:
            return _error_response(str(e), status=500)

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
            provider = data.get("provider", "")
            model = data.get("model", "gpt-4o")
            language = data.get("language", "en")
            privacy_mode = data.get("privacy_mode", "basic")  # S6: PII sanitization level

            logger.info(f"Analyze API called - error_length={len(error_text) if error_text else 0}, has_workflow={bool(workflow)}, model={model}, privacy={privacy_mode}")

            # S2: SSRF protection - validate base URL
            is_valid, ssrf_error = validate_ssrf_url(base_url)
            if not is_valid:
                logger.warning(f"SSRF blocked: {ssrf_error}")
                return _error_response(f"Invalid Base URL: {ssrf_error}", status=400, code="invalid_base_url")

            # Resolve API key via request -> ENV -> server store
            api_key, key_source, resolved_provider, is_local = resolve_api_key(
                base_url=base_url,
                provider_hint=provider,
                request_api_key=api_key,
            )
            if not api_key and not is_local:
                return _error_response("Missing API Key", status=401, code="missing_api_key")
            logger.info(f"Analyze key source={key_source}, provider={resolved_provider or 'unknown'}, local={is_local}")

            if not error_text:
                return _error_response("No error text provided", status=400, code="missing_error_text")

            # S6: PII Sanitization - Remove sensitive info before sending to LLM
            sanitizer, downgraded = get_outbound_sanitizer(base_url, privacy_mode)
            if downgraded:
                logger.warning("privacy_mode=none is only allowed for verified local providers; using basic")

            # Sanitize error text
            sanitization_result = sanitizer.sanitize(error_text)
            error_text = sanitization_result.sanitized_text

            # Log sanitization metadata (for audit)
            if sanitization_result.pii_found:
                logger.info(f"PII sanitized: {sanitization_result.replacements}")

            # Sanitize node context (paths, custom_node_path)
            if node_context:
                node_context = sanitizer.sanitize_dict(node_context, keys_to_sanitize=[])

            # Truncate error text to prevent token overflow (roughly 8000 chars ≈ 2000 tokens)
            MAX_ERROR_LENGTH = 8000
            if len(error_text) > MAX_ERROR_LENGTH:
                error_text = error_text[:MAX_ERROR_LENGTH] + "\n\n[... truncated ...]"

            # R8: Smart workflow truncation (preserves error-related nodes)
            if workflow:
                from .truncate_workflow import truncate_workflow_smart
                error_node_id = (
                    node_context.get("display_node")
                    or node_context.get("node_id")
                    or node_context.get("real_node_id")
                    or node_context.get("id")
                ) if node_context else None
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
                "- **Missing Models**: Check if the model exists in a configured or registered model folder, verify filename spelling\n"
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

            # R14: Use PromptComposer for unified context formatting
            if CONFIG.r14_use_prompt_composer:
                try:
                    pipeline_context = ErrorAnalyzer.build_llm_context(
                        error_text,
                        workflow_json=workflow,
                        node_context=node_context,
                        settings={"privacy_mode": privacy_mode},
                    )
                    llm_context = pipeline_context.llm_context or {
                        "traceback": error_text,
                        "node_info": node_context if node_context else {},
                    }

                    composer_config = PromptComposerConfig(use_legacy_format=CONFIG.r14_use_legacy_format)
                    prompt_composer = get_prompt_composer()
                    user_prompt = prompt_composer.compose(llm_context, composer_config)

                    logger.info("[R14] PromptComposer used for /doctor/analyze")
                except Exception as r14_err:
                    logger.warning(f"[R14] PromptComposer failed in /doctor/analyze, falling back to legacy: {r14_err}")
                    # Fall through to legacy format
                    user_prompt = None
            else:
                user_prompt = None

            # Legacy format (fallback or when R14 disabled)
            if user_prompt is None:
                user_prompt = f"Error:\n{error_text}\n\n"
                if node_context:
                    user_prompt += f"Node Context: {json.dumps(node_context, indent=2)}\n\n"

                # F3: Include workflow context if available
                if workflow:
                    user_prompt += f"Workflow Structure (simplified):\n{workflow}\n\n"

                # F10: Include system environment context for better debugging
                try:
                    env_info = get_system_environment()
                    env_text = format_env_for_llm(env_info, max_packages=30)
                    user_prompt += f"{env_text}\n\n"
                except Exception as env_err:
                    # Don't fail the entire analysis if env collection fails
                    logger.warning(f"Failed to collect environment info: {env_err}")
                    user_prompt += "[System environment info unavailable]\n\n"

            # Normalize Base URL
            base_url = base_url.rstrip("/")
            is_local = is_local_llm_url(base_url)
            llm_adapter = get_llm_provider_adapter(base_url, is_local=is_local)
            provider_request = llm_adapter.build_chat_request(
                base_url,
                api_key,
                model,
                system_prompt,
                [{"role": "user", "content": user_prompt}],
                stream=False,
                temperature=0.5,
            )
            url = provider_request.url
            headers = provider_request.headers
            payload = provider_request.payload

            # R7: Rate limit check (core limiter for heavy endpoint)
            if not SessionManager.get_core_limiter().allow():
                logger.warning("Rate limit exceeded for /doctor/analyze")
                return _error_response(
                    "Rate limit exceeded. Please wait before retrying.",
                    status=429,
                    code="rate_limited",
                )

            # R7: Concurrency limit (prevent connection pool exhaustion)
            async with SessionManager.get_concurrency_limiter():
                session = await SessionManager.get_session()
                payload = sanitize_outbound_payload(payload, sanitizer)

                # R6: Request with retry logic
                retry_config = RetryConfig(
                    max_retries=CONFIG.llm_max_retries,
                    request_timeout_seconds=CONFIG.llm_request_timeout,
                    total_timeout_seconds=CONFIG.llm_total_timeout,
                    retry_on_5xx=False,  # Conservative for non-streaming
                )
                result = await llm_request_with_retry(
                    session, "POST", url,
                    json=payload, headers=headers,
                    config=retry_config,
                )

                if not result.success:
                    _close_retry_response(result)
                    error_msg = result.error or "Unknown error"
                    logger.error(f"LLM request failed after {result.attempts} attempts: {error_msg}")
                    return _error_response(f"LLM Error: {error_msg}", status=503, code="llm_error")

                async with result.response as response:
                    if response.status != 200:
                        error_msg = await response.text()
                        # Truncate error message for readability
                        if len(error_msg) > 500:
                            error_msg = error_msg[:500] + "..."
                        return _error_response(
                            f"LLM Provider Error ({response.status}): {error_msg}",
                            status=response.status,
                            code="llm_provider_error",
                        )

                    # Safely parse JSON response
                    try:
                        resp_data = await response.json()
                        content = llm_adapter.parse_chat_response(resp_data)
                        if not content:
                            return _error_response("Empty response from LLM", status=502, code="empty_llm_response")

                        # R19: Clean output (strip hidden reasoning)
                        from .services.providers.base import BaseProviderAdapter
                        content = BaseProviderAdapter.clean_llm_output(content)

                        logger.info(f"Analysis successful, response length={len(content)}, attempts={result.attempts}")
                        return web.json_response({"analysis": content})
                    except (json.JSONDecodeError, KeyError, IndexError) as parse_err:
                        return _error_response(
                            f"Failed to parse LLM response: {str(parse_err)}",
                            status=502,
                            code="llm_parse_error",
                        )

        except aiohttp.ClientError as e:
            # Network-level errors (timeout, connection refused, etc.)
            logger.error(f"LLM Network Error: {str(e)}")
            return _error_response(f"Network Error: {str(e)}", status=503, code="network_error")
        except Exception as e:
            logger.error(f"LLM Analysis Failed: {str(e)}")
            return _error_response(str(e), status=500)

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
            provider = data.get("provider", "")
            model = data.get("model", "gpt-4o")
            language = data.get("language", "en")
            stream = data.get("stream", True)
            intent = data.get("intent", "chat")  # New: intent parameter
            selected_nodes = data.get("selected_nodes", [])  # New: node selection context
            privacy_mode = data.get("privacy_mode", "basic")  # S6: PII sanitization level

            logger.info(f"Chat API called - model={model}, intent={intent}, messages={len(messages)}, stream={stream}, privacy={privacy_mode}")

            # S2: SSRF protection - validate base URL
            is_valid, ssrf_error = validate_ssrf_url(base_url)
            if not is_valid:
                logger.warning(f"SSRF blocked: {ssrf_error}")
                return _error_response(f"Invalid Base URL: {ssrf_error}", status=400, code="invalid_base_url")

            # Resolve API key via request -> ENV -> server store
            api_key, key_source, resolved_provider, is_local = resolve_api_key(
                base_url=base_url,
                provider_hint=provider,
                request_api_key=api_key,
            )
            if not api_key and not is_local:
                return _error_response("Missing API Key", status=401, code="missing_api_key")
            logger.info(f"Chat key source={key_source}, provider={resolved_provider or 'unknown'}, local={is_local}")

            if not messages:
                return _error_response("No messages provided", status=400, code="missing_messages")

            # R12: Smart Token Budget
            # Apply budget metrics and trimming BEFORE sanitization and prompt construction
            # This ensures we operate on the raw context keys
            # Supports both remote (strict) and local (opt-in soft) modes
            r12_meta = {}
            r12_should_apply = (CONFIG.r12_enabled_remote and not is_local) or (CONFIG.r12_enabled_local and is_local)

            if r12_should_apply:
                try:
                    from .services.token_estimator import EstimatorConfig

                    # Select appropriate limits and policy based on provider type
                    if is_local:
                        # Local mode: use local limits with local_soft policy
                        soft_max = CONFIG.r12_soft_max_tokens_local
                        hard_max = CONFIG.r12_hard_max_tokens_local
                        policy = "local_soft"
                    else:
                        # Remote mode: use remote limits with configured policy
                        soft_max = CONFIG.r12_soft_max_tokens_remote
                        hard_max = CONFIG.r12_hard_max_tokens_remote
                        policy = CONFIG.r12_policy_profile

                    budget_config = BudgetConfig(
                        enabled_remote=CONFIG.r12_enabled_remote,
                        enabled_local=CONFIG.r12_enabled_local,
                        soft_max_tokens=soft_max,
                        hard_max_tokens=hard_max,
                        trimming_policy=policy,
                        estimator_config=EstimatorConfig(
                            chars_per_token=CONFIG.r12_estimator_fallback_cpt,
                            safety_multiplier=CONFIG.r12_estimator_safety_mult
                        ),
                        prune_default_depth=CONFIG.r12_prune_default_depth,
                        prune_default_nodes=CONFIG.r12_prune_default_nodes,
                        overhead_fixed=CONFIG.r12_overhead_fixed
                    )

                    # Create context wrapper
                    budget_context = {
                        "messages": messages,
                        "error_context": error_context
                    }

                    # Apply
                    budgeted_context, r12_meta = TOKEN_BUDGET_SERVICE.apply_token_budget(
                        budget_context,
                        is_remote_provider=not is_local,
                        config=budget_config
                    )

                    # Update local refs with trimmed versions
                    if "messages" in budgeted_context:
                        messages = budgeted_context["messages"]
                    if "error_context" in budgeted_context:
                        error_context = budgeted_context["error_context"]
                except Exception as r12_err:
                    logger.warning(f"R12 Budget application failed, proceeding with original payload: {r12_err}")

            # S6: PII Sanitization - Remove sensitive info before sending to LLM
            sanitizer, downgraded = get_outbound_sanitizer(base_url, privacy_mode)
            if downgraded:
                logger.warning("privacy_mode=none is only allowed for verified local providers; using basic")

            # Build system prompt with error context
            # R14: Support both "error" and "last_error" keys for compatibility
            error_text = error_context.get("error") or error_context.get("last_error", "")
            node_context = error_context.get("node_context", {})
            workflow = error_context.get("workflow", "")

            # Sanitize error context
            if error_text:
                error_text = sanitizer.sanitize(error_text).sanitized_text
            if node_context:
                node_context = sanitizer.sanitize_dict(node_context, keys_to_sanitize=[])

            # Sanitize user messages (only user role, not assistant responses)
            for msg in messages:
                if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                    msg["content"] = sanitizer.sanitize(msg["content"]).sanitized_text

            # Truncate to prevent token overflow
            MAX_ERROR_LENGTH = 4000
            if len(error_text) > MAX_ERROR_LENGTH:
                error_text = error_text[:MAX_ERROR_LENGTH] + "\n[... truncated ...]"

            # R8: Smart workflow truncation
            if workflow:
                from .truncate_workflow import truncate_workflow_smart
                workflow, _ = truncate_workflow_smart(workflow, max_chars=2000)

            # Option B Phase 1: Parse workflow data for enhanced error context
            workflow_data = None
            if workflow:
                try:
                    # If workflow is a JSON string, parse it
                    if isinstance(workflow, str):
                        workflow_data = json.loads(workflow)
                    elif isinstance(workflow, dict):
                        workflow_data = workflow
                except json.JSONDecodeError:
                    logger.warning("Failed to parse workflow JSON for enhanced context")

            # Option B Phase 1: Collect enhanced error context
            # R14: Support both "error" and "last_error" keys
            enriched_context = None
            canonical_error = error_context.get("error") or error_context.get("last_error")
            if error_context and canonical_error:
                # Build error_data dict from error_context
                error_data = {
                    "exception_message": canonical_error,
                    "exception_type": error_context.get("error_type", "Unknown"),
                    "node_id": node_context.get("node_id") if node_context else None,
                    "display_node": node_context.get("display_node") if node_context else None,
                    "parent_node": node_context.get("parent_node") if node_context else None,
                    "real_node_id": node_context.get("real_node_id") if node_context else None,
                    "subgraph_lineage": node_context.get("subgraph_lineage") if node_context else None,
                    "traceback": error_context.get("traceback")
                }
                enriched_context = collect_error_context(error_data, workflow_data)

            error_category = None
            if error_context and canonical_error:
                # Categorize using the full error_context dict for better keyword matching
                error_category = categorize_error(error_context)
                logger.info(f"Error categorized as: {error_category['category']} (confidence: {error_category['confidence']:.0%})")

            # Option B Phase 1: Detect user's preferred language from request headers or data
            user_lang_code = language  # Default to language parameter
            if not user_lang_code or user_lang_code not in ["en", "zh_TW", "zh_CN", "ja", "de", "fr", "it", "es", "ko"]:
                # Try to parse from Accept-Language header if available
                accept_lang = request.headers.get("Accept-Language", "en")
                user_lang_code = parse_language_code(accept_lang)

            # Intent-aware system prompt
            if intent == "explain_node":
                # Node explanation mode - use simple prompt
                system_prompt = (
                    "You are an expert ComfyUI node documentation assistant. ComfyUI is a node-based Stable Diffusion workflow editor.\n\n"
                    "Your task is to explain how specific nodes work, their inputs/outputs, and best practices for using them.\n"
                    "Be concise, clear, and provide practical examples when relevant.\n"
                    f"Respond in {language}.\n\n"
                )
                if selected_nodes:
                    system_prompt += f"**Selected Node(s):** {json.dumps(selected_nodes)}\n\n"
            else:
                # Option B Phase 1: Error analysis mode - use enhanced multi-language template
                if enriched_context and enriched_context.get("error_message"):
                    # Use enhanced error analysis template with language directive
                    system_prompt = get_error_analysis_prompt(user_lang_code)

                    # R14: Use PromptComposer for unified context formatting
                    r14_composer_succeeded = False  # Track success for fallback logic
                    if CONFIG.r14_use_prompt_composer:
                        try:
                            r14_composer_succeeded = True  # Assume success until exception
                            traceback_text = str(enriched_context.get('traceback') or '')
                            failed_node = enriched_context.get('failed_node', {})
                            pipeline_node_context = {
                                "node_id": failed_node.get('id') or node_context.get('node_id'),
                                "node_name": failed_node.get('title') or node_context.get('node_name'),
                                "node_class": failed_node.get('class_type') or node_context.get('node_class'),
                                "display_node": failed_node.get('display_node') or node_context.get('display_node'),
                                "parent_node": failed_node.get('parent_node') or node_context.get('parent_node'),
                                "real_node_id": failed_node.get('real_node_id') or node_context.get('real_node_id'),
                            }
                            pipeline_context = ErrorAnalyzer.build_llm_context(
                                traceback_text or enriched_context['error_message'],
                                workflow_json=workflow_data or workflow,
                                node_context=pipeline_node_context,
                                execution_logs=enriched_context.get('execution_logs', []),
                                settings={"privacy_mode": privacy_mode},
                            )
                            llm_context = pipeline_context.llm_context or {
                                "error_summary": enriched_context['error_message'],
                                "node_info": pipeline_node_context,
                                "traceback": traceback_text,
                                "execution_logs": enriched_context.get('execution_logs', []),
                                "workflow_subset": enriched_context.get('workflow_structure'),
                            }

                            composer_config = PromptComposerConfig(use_legacy_format=CONFIG.r14_use_legacy_format)
                            prompt_composer = get_prompt_composer()
                            context_block = prompt_composer.compose(llm_context, composer_config)

                            system_prompt += f"\n\n{context_block}"

                            # Add error category if available
                            if error_category:
                                system_prompt += f"\n\n**ERROR CATEGORY** (auto-detected):\n"
                                system_prompt += f"Category: {error_category['category']}\n"
                                system_prompt += f"Confidence: {error_category['confidence']:.0%}\n"
                                system_prompt += f"Suggested Approach: {error_category['suggested_approach']}\n"

                            logger.info("[R14/R15] PromptComposer used for context formatting with canonical system_info")
                        except Exception as r14_err:
                            logger.warning(f"[R14] PromptComposer failed, falling back to legacy: {r14_err}")
                            # R14: Use local flag, NOT global CONFIG mutation
                            r14_composer_succeeded = False
                    else:
                        r14_composer_succeeded = False

                    # Legacy format (fallback or when R14 disabled)
                    if not r14_composer_succeeded:
                        # Add enriched error context (legacy format)
                        system_prompt += f"\n\n**ERROR CONTEXT**:\n"
                        system_prompt += f"Error Type: {enriched_context['error_type']}\n"
                        system_prompt += f"Error Message: {enriched_context['error_message']}\n"

                        # Option B Phase 2: Add error category with suggested approach
                        if error_category:
                            system_prompt += f"\n**ERROR CATEGORY** (auto-detected):\n"
                            system_prompt += f"Category: {error_category['category']}\n"
                            system_prompt += f"Confidence: {error_category['confidence']:.0%}\n"
                            system_prompt += f"Suggested Approach: {error_category['suggested_approach']}\n"
                            if error_category['keywords_matched']:
                                matched_kw_str = ', '.join(error_category['keywords_matched'][:5])  # Limit to 5
                                system_prompt += f"Matched Keywords: {matched_kw_str}\n"

                        if enriched_context.get('traceback'):
                            # Truncate traceback to prevent token overflow
                            traceback_text = str(enriched_context['traceback'])
                            if len(traceback_text) > 2000:
                                traceback_text = traceback_text[:2000] + "\n[... truncated ...]"
                            system_prompt += f"\nPython Stack Trace:\n```\n{traceback_text}\n```\n"

                        if enriched_context.get('failed_node'):
                            node = enriched_context['failed_node']
                            system_prompt += f"\nFailed Node: {node['class_type']} (ID: {node['id']})\n"
                            if node.get('title'):
                                system_prompt += f"Node Title: {node['title']}\n"
                            system_prompt += f"Node Inputs: {json.dumps(node['inputs'], indent=2)}\n"

                        if enriched_context['workflow_structure'].get('upstream_nodes'):
                            upstream_nodes = enriched_context['workflow_structure']['upstream_nodes']
                            system_prompt += f"\nUpstream Nodes: {len(upstream_nodes)} connected\n"
                            for up in upstream_nodes[:5]:  # Limit to 5 to prevent token overflow
                                system_prompt += f"  - {up['class_type']} -> {up['connection']}\n"

                        if enriched_context['workflow_structure'].get('missing_connections'):
                            system_prompt += "\nMissing Required Connections:\n"
                            for missing in enriched_context['workflow_structure']['missing_connections']:
                                system_prompt += f"  - {missing['input']} (type: {missing['type']})\n"
                else:
                    # Fallback to simple chat/debug prompt
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

            # F10/R15: Include system environment context
            # R15: Only append legacy format if PromptComposer was NOT used (avoid duplicate env)
            if not r14_composer_succeeded:
                try:
                    env_info = get_system_environment()
                    env_text = format_env_for_llm(env_info, max_packages=20)
                    system_prompt += f"\n{env_text}\n\n"
                except Exception as env_err:
                    logger.warning(f"Failed to collect environment info for chat: {env_err}")

            # Prepare request
            base_url = base_url.rstrip("/")
            is_local = is_local_llm_url(base_url)

            # Limit conversation history to prevent token overflow
            MAX_HISTORY = 10
            recent_messages = messages[-MAX_HISTORY:] if len(messages) > MAX_HISTORY else messages
            llm_adapter = get_llm_provider_adapter(base_url, is_local=is_local)
            provider_request = llm_adapter.build_chat_request(
                base_url,
                api_key,
                model,
                system_prompt,
                recent_messages,
                stream=stream,
                temperature=0.7,
            )
            url = provider_request.url
            headers = provider_request.headers
            payload = provider_request.payload

            logger.info(f"Connecting to LLM: {url}")

            # R7: Rate limit check (core limiter for heavy endpoint)
            if not SessionManager.get_core_limiter().allow():
                logger.warning("Rate limit exceeded for /doctor/chat")
                return _error_response(
                    "Rate limit exceeded. Please wait before retrying.",
                    status=429,
                    code="rate_limited",
                )

            # R7: Concurrency limit (prevent connection pool exhaustion)
            async with SessionManager.get_concurrency_limiter():
                if not stream:
                    # Non-streaming fallback with retry
                    session = await SessionManager.get_session()
                    payload = sanitize_outbound_payload(payload, sanitizer)

                    # R6: Request with retry logic
                    retry_config = RetryConfig(
                        max_retries=CONFIG.llm_max_retries,
                        request_timeout_seconds=CONFIG.llm_request_timeout,
                        total_timeout_seconds=CONFIG.llm_total_timeout,
                        retry_on_5xx=False,
                    )
                    result = await llm_request_with_retry(
                        session, "POST", url,
                        json=payload, headers=headers,
                        config=retry_config,
                    )

                    if not result.success:
                        _close_retry_response(result)
                        error_msg = result.error or "Unknown error"
                        logger.error(f"LLM non-stream failed after {result.attempts} attempts: {error_msg}")
                        return _error_response(f"LLM Error: {error_msg}", status=503, code="llm_error")

                    async with result.response as response:
                        if response.status != 200:
                            error_msg = await response.text()
                            logger.error(f"LLM non-stream error: {error_msg[:200]}")
                            return _error_response(f"LLM Error: {error_msg[:500]}", status=response.status, code="llm_error")

                        resp_data = await response.json()
                        content = llm_adapter.parse_chat_response(resp_data)
                        # R19: Clean output (strip hidden reasoning)
                        from .services.providers.base import BaseProviderAdapter
                        content = BaseProviderAdapter.clean_llm_output(content)

                        logger.info(f"LLM response received (non-stream), length={len(content)}, attempts={result.attempts}")
                        return web.json_response({"content": content, "done": True, "metadata": r12_meta})

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

                # Send R12 metadata as early SSE event if available
                if r12_meta:
                    meta_event = json.dumps({"type": "usage_metadata", "data": r12_meta})
                    await response.write(f"data: {meta_event}\n\n".encode('utf-8'))

                try:
                    session = await SessionManager.get_session()
                    payload = sanitize_outbound_payload(payload, sanitizer)

                    # R6: Pre-stream retry (only retry before streaming starts)
                    # Once streaming begins, we cannot retry
                    retry_config = RetryConfig(
                        max_retries=CONFIG.llm_max_retries,
                        request_timeout_seconds=CONFIG.llm_request_timeout,
                        total_timeout_seconds=CONFIG.llm_total_timeout,
                        retry_on_5xx=False,
                    )
                    result = await llm_request_with_retry(
                        session, "POST", url,
                        json=payload, headers=headers,
                        config=retry_config,
                        is_streaming=True,
                    )

                    if not result.success or result.response is None:
                        _close_retry_response(result)
                        error_msg = result.error or "Unknown error"
                        logger.error(f"LLM stream connection failed after {result.attempts} attempts: {error_msg}")
                        error_data = json.dumps({"error": f"LLM Error: {error_msg}", "done": True})
                        await response.write(f"data: {error_data}\n\n".encode('utf-8'))
                        return response

                    # Note: From here on, NO RETRY - streaming has begun
                    async with result.response as llm_response:
                        if llm_response.status != 200:
                            error_msg = await llm_response.text()
                            logger.error(f"LLM stream error: {error_msg[:200]}")
                            error_data = json.dumps({"error": f"LLM Error: {error_msg[:200]}", "done": True})
                            await response.write(f"data: {error_data}\n\n".encode('utf-8'))
                            return response

                        # Stream chunks with newline buffering to handle partial lines
                        buffer = ""
                        stream_done = False
                        # F7: Accumulate full content for fix detection
                        full_content = ""
                        async for chunk in llm_response.content.iter_chunked(1024):
                            buffer += chunk.decode('utf-8', errors='ignore')

                            while '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                                line = line.strip()
                                if not line:
                                    continue

                                try:
                                    parsed_chunk = llm_adapter.parse_stream_line(line)
                                except json.JSONDecodeError:
                                    continue

                                if parsed_chunk.done:
                                    done_data = json.dumps({"delta": "", "done": True})
                                    await response.write(f"data: {done_data}\n\n".encode('utf-8'))
                                    stream_done = True
                                    break
                                if parsed_chunk.skip or not parsed_chunk.delta:
                                    continue

                                full_content += parsed_chunk.delta  # F7: Accumulate
                                chunk_data = json.dumps({"delta": parsed_chunk.delta, "done": False})
                                await response.write(f"data: {chunk_data}\n\n".encode('utf-8'))

                            if stream_done:
                                break

                    # Process any remaining buffered line if stream ended without newline
                    if not stream_done and buffer.strip():
                        line = buffer.strip()
                        try:
                            parsed_chunk = llm_adapter.parse_stream_line(line)
                            if parsed_chunk.done:
                                done_data = json.dumps({"delta": "", "done": True})
                                await response.write(f"data: {done_data}\n\n".encode('utf-8'))
                            elif not parsed_chunk.skip and parsed_chunk.delta:
                                full_content += parsed_chunk.delta  # F7: Accumulate
                                chunk_data = json.dumps({"delta": parsed_chunk.delta, "done": False})
                                await response.write(f"data: {chunk_data}\n\n".encode('utf-8'))
                        except json.JSONDecodeError:
                            pass

                    # F7: Detect and send fix suggestions after stream completes
                    if full_content:
                        import re
                        FIX_PATTERN = re.compile(r'```json\s*(\{[^`]*?"fixes"[^`]*?\})\s*```', re.DOTALL)
                        fix_match = FIX_PATTERN.search(full_content)

                        if fix_match:
                            try:
                                fix_json = json.loads(fix_match.group(1))
                                if validate_fix_schema(fix_json):
                                    # Send as separate SSE event
                                    fix_data = json.dumps({
                                        "type": "fix_suggestion",
                                        "data": fix_json
                                    })
                                    await response.write(f"data: {fix_data}\n\n".encode('utf-8'))
                            except json.JSONDecodeError:
                                pass  # Invalid JSON, ignore

                except Exception as stream_err:
                    error_data = json.dumps({"error": str(stream_err), "done": True})
                    await response.write(f"data: {error_data}\n\n".encode('utf-8'))

            return response

        except aiohttp.ClientError as e:
            emit_doctor_log(f"Chat network error: {e}", "ERROR")
            return _error_response(f"Network Error: {str(e)}", status=503, code="network_error")
        except Exception as e:
            emit_doctor_log(f"Chat failed: {e}", "ERROR")
            return _error_response(str(e), status=500)

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
            return _error_response(str(e), status=500)

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
            "anthropic": "https://api.anthropic.com",
            "deepseek": "https://api.deepseek.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
            "xai": "https://api.x.ai/v1",
            "openrouter": "https://openrouter.ai/api/v1"
        })

    @server.PromptServer.instance.routes.get("/doctor/secrets/status")
    async def api_secrets_status(request):
        """
        Get provider key status without exposing secret values.
        Admin-gated to prevent leaking configuration sources.
        """
        try:
            # S8: read-only guard — loopback convenience, remote needs token
            allowed, code, message = validate_admin_request(request)
            if not allowed:
                return _admin_denied_response(code, message)

            providers = get_provider_status()
            return web.json_response({
                "success": True,
                "providers": providers,
            })
        except Exception as e:
            logger.error(f"Secrets status API error: {e}")
            return _error_response(str(e), status=500)

    @server.PromptServer.instance.routes.put("/doctor/secrets")
    async def api_secrets_put(request):
        """
        Save a provider secret to server-side secret store.
        Body: {"provider": "openai|...|generic", "api_key": "...", "admin_token"?: "..."}
        """
        try:
            data = await request.json()
        except Exception:
            return _error_response("Invalid JSON", status=400, code="invalid_json")

        allowed, code, message = validate_admin_request(request, payload=data)
        if not allowed:
            return _admin_denied_response(code, message)

        provider = (data.get("provider") or "").strip().lower()
        api_key = (data.get("api_key") or "").strip()
        if not provider:
            return _error_response("Missing provider", status=400, code="missing_provider")
        if not api_key:
            return _error_response("Missing api_key", status=400, code="missing_api_key")

        valid_providers = {"openai", "anthropic", "deepseek", "groq", "gemini", "xai", "openrouter", "generic"}
        if provider not in valid_providers:
            return _error_response("Invalid provider", status=400, code="invalid_provider")

        try:
            get_secret_store().set_secret(provider, api_key)
            logger.info(f"Secret saved for provider={provider}")
            return web.json_response({"success": True, "message": "Secret saved"})
        except Exception as e:
            logger.error(f"Secrets put API error: {e}")
            return _error_response(str(e), status=500)

    @server.PromptServer.instance.routes.delete("/doctor/secrets/{provider}")
    async def api_secrets_delete(request):
        """
        Delete a provider secret from server-side secret store.
        Auth: admin token in header/body policy handled by admin guard.
        """
        provider = (request.match_info.get("provider") or "").strip().lower()
        if not provider:
            return _error_response("Missing provider", status=400, code="missing_provider")

        # For DELETE we read optional JSON body if present, but also support headers-only.
        payload = {}
        try:
            if request.can_read_body:
                payload = await request.json()
        except Exception:
            payload = {}

        allowed, code, message = validate_admin_request(request, payload=payload)
        if not allowed:
            return _admin_denied_response(code, message)

        try:
            deleted = get_secret_store().clear_secret(provider)
            if not deleted:
                return _error_response("Not found", status=404, code="not_found")
            logger.info(f"Secret deleted for provider={provider}")
            return web.json_response({"success": True, "message": "Secret deleted"})
        except Exception as e:
            logger.error(f"Secrets delete API error: {e}")
            return _error_response(str(e), status=500)

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
            provider = data.get("provider", "")

            # S2: SSRF protection - validate base URL
            is_valid, ssrf_error = validate_ssrf_url(base_url)
            if not is_valid:
                logger.warning(f"SSRF blocked in verify_key: {ssrf_error}")
                return _error_response(
                    f"Invalid Base URL: {ssrf_error}",
                    status=200,
                    code="invalid_base_url",
                    extra={"is_local": False},
                )

            api_key, key_source, resolved_provider, is_local = resolve_api_key(
                base_url=base_url,
                provider_hint=provider,
                request_api_key=api_key,
            )
            if not api_key and not is_local:
                return _error_response(
                    "No API key provided",
                    status=200,
                    code="missing_api_key",
                    extra={"is_local": False},
                )
            logger.info(f"Verify key source={key_source}, provider={resolved_provider or 'unknown'}, local={is_local}")

            # Normalize base URL
            base_url = base_url.rstrip("/")

            # Use placeholder for local LLMs without key
            if is_local and not api_key:
                api_key = _local_llm_auth_placeholder()

            llm_adapter = get_llm_provider_adapter(base_url, is_local=is_local)
            provider_request = llm_adapter.build_models_request(base_url, api_key)

            # R7: Rate limit check (light limiter for quick requests)
            if not SessionManager.get_light_limiter().allow():
                logger.warning("Rate limit exceeded for /doctor/verify_key")
                return _error_response(
                    "Rate limit exceeded. Please wait before retrying.",
                    status=200,
                    code="rate_limited",
                    extra={"is_local": is_local},
                )

            session = await SessionManager.get_session()
            async with session.get(provider_request.url, headers=provider_request.headers, allow_redirects=False) as response:
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
                    return _error_response(
                        f"Verification failed ({response.status}): {error_text}",
                        status=200,
                        code="verification_failed",
                        extra={"is_local": is_local},
                    )

        except aiohttp.ClientError as e:
            return _error_response(
                f"Connection error: {str(e)}",
                status=200,
                code="connection_error",
                extra={"is_local": is_local_llm_url(data.get("base_url", "")) if 'data' in locals() else False},
            )
        except Exception as e:
            return _error_response(f"Error: {str(e)}", status=200, extra={"is_local": False})

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
            provider = data.get("provider", "")

            # S2: SSRF protection - validate base URL
            is_valid, ssrf_error = validate_ssrf_url(base_url)
            if not is_valid:
                logger.warning(f"SSRF blocked in list_models: {ssrf_error}")
                return _error_response(
                    f"Invalid Base URL: {ssrf_error}",
                    status=200,
                    code="invalid_base_url",
                    extra={"models": []},
                )

            api_key, key_source, resolved_provider, is_local = resolve_api_key(
                base_url=base_url,
                provider_hint=provider,
                request_api_key=api_key,
            )
            if not api_key and not is_local:
                return _error_response(
                    "No API key provided",
                    status=200,
                    code="missing_api_key",
                    extra={"models": []},
                )
            logger.info(f"List-models key source={key_source}, provider={resolved_provider or 'unknown'}, local={is_local}")

            base_url = base_url.rstrip("/")
            if is_local and not api_key:
                api_key = _local_llm_auth_placeholder()

            llm_adapter = get_llm_provider_adapter(base_url, is_local=is_local)
            provider_request = llm_adapter.build_models_request(base_url, api_key)

            # R7: Rate limit check (light limiter for quick requests)
            if not SessionManager.get_light_limiter().allow():
                logger.warning("Rate limit exceeded for /doctor/list_models")
                return _error_response(
                    "Rate limit exceeded. Please wait before retrying.",
                    status=200,
                    code="rate_limited",
                    extra={"models": []},
                )

            session = await SessionManager.get_session()
            async with session.get(provider_request.url, headers=provider_request.headers, allow_redirects=False) as response:
                if response.status != 200:
                    return _error_response(
                        f"Failed to fetch models ({response.status})",
                        status=200,
                        code="model_fetch_failed",
                        extra={"models": []},
                    )

                try:
                    result = await response.json()
                    models = llm_adapter.parse_models_response(result)

                    logger.info(f"Retrieved {len(models)} models from {provider_request.url}")
                    return web.json_response({
                        "success": True,
                        "models": models,
                        "message": f"Found {len(models)} models"
                    })

                except (json.JSONDecodeError, KeyError) as e:
                    return _error_response(
                        f"Failed to parse model list: {str(e)}",
                        status=200,
                        code="model_parse_failed",
                        extra={"models": []},
                    )

        except aiohttp.ClientError as e:
            return _error_response(
                f"Connection error: {str(e)}",
                status=200,
                code="connection_error",
                extra={"models": []},
            )
        except Exception as e:
            return _error_response(f"Error: {str(e)}", status=200, extra={"models": []})

    # ---- F4: Statistics Dashboard API Endpoints ----

    @server.PromptServer.instance.routes.get("/doctor/statistics")
    async def api_get_statistics(request):
        """
        API endpoint to get error statistics for dashboard.

        Query params: ?time_range_days=30 (default: 30)

        Returns: {
            "success": bool,
            "statistics": {
                "total_errors": int,
                "pattern_frequency": {pattern_id: count},
                "category_breakdown": {category: count},
                "top_patterns": [{pattern_id, count, category}],
                "resolution_rate": {resolved, unresolved, ignored},
                "trend": {last_24h, last_7d, last_30d}
            }
        }
        """
        try:
            from .statistics import StatisticsCalculator

            time_range_days = int(request.query.get("time_range_days", 30))

            # Get history from SmartLogger
            history = get_analysis_history()

            # Calculate statistics
            statistics = StatisticsCalculator.calculate(history, time_range_days)

            logger.info(f"Statistics calculated: total_errors={statistics['total_errors']}, time_range={time_range_days}d")

            return web.json_response({
                "success": True,
                "statistics": statistics
            })
        except Exception as e:
            logger.error(f"Statistics API error: {str(e)}")
            return _error_response(
                str(e),
                status=500,
                extra={
                    "statistics": {
                    "total_errors": 0,
                    "pattern_frequency": {},
                    "category_breakdown": {},
                    "top_patterns": [],
                    "resolution_rate": {"resolved": 0, "unresolved": 0, "ignored": 0},
                    "trend": {"last_24h": 0, "last_7d": 0, "last_30d": 0}
                    }
                },
            )

    @server.PromptServer.instance.routes.post("/doctor/statistics/reset")
    async def api_reset_statistics(request):
        """
        API endpoint to reset statistics (clears all error history).

        Returns: {"success": bool, "message": str}
        """
        payload = {}
        try:
            if request.can_read_body:
                payload = await request.json()
        except Exception:
            payload = {}

        # CRITICAL: write-sensitive endpoint must remain admin-gated.
        allowed, code, message = validate_admin_request(request, payload=payload)
        if not allowed:
            return _admin_denied_response(code, message)

        try:
            success = clear_analysis_history()
            if success:
                logger.info("Statistics reset (history cleared)")
                return web.json_response({"success": True, "message": "Statistics reset successfully"})
            else:
                return _error_response("Failed to clear history", status=500, code="clear_history_failed")
        except Exception as e:
            logger.error(f"Statistics reset API error: {str(e)}")
            return _error_response(str(e), status=500)

    @server.PromptServer.instance.routes.post("/doctor/mark_resolved")
    async def api_mark_error_resolved(request):
        """
        API endpoint to mark an error as resolved/unresolved/ignored.

        Body: {
            "timestamp": "2026-01-04T12:00:00",
            "status": "resolved"|"unresolved"|"ignored"
        }

        Returns: {"success": bool, "message": str}
        """
        try:
            data = await request.json()
        except Exception:
            return _error_response("Invalid JSON", status=400, code="invalid_json")

        # CRITICAL: write-sensitive endpoint must remain admin-gated.
        allowed, code, message = validate_admin_request(request, payload=data)
        if not allowed:
            return _admin_denied_response(code, message)

        try:
            timestamp = data.get("timestamp")
            status = data.get("status", "resolved")

            if not timestamp:
                return _error_response("Missing timestamp", status=400, code="missing_timestamp")

            if status not in ["resolved", "unresolved", "ignored"]:
                return _error_response("Invalid status", status=400, code="invalid_status")

            from .logger import update_resolution_status

            if update_resolution_status(timestamp, status):
                logger.info(f"Error marked as {status}: {timestamp}")
                return web.json_response({"success": True, "message": f"Error marked as {status}"})

            return _error_response("Timestamp not found", status=404, code="not_found")

        except Exception as e:
            logger.error(f"Mark resolved API error: {str(e)}")
            return _error_response(str(e), status=500)

    # ---- F16: Quick Community Feedback (GitHub PR) ----

    @server.PromptServer.instance.routes.post("/doctor/feedback/preview")
    async def api_feedback_preview(request):
        """
        F16 preview endpoint (read-only): validate + sanitize community feedback payload.
        Returns sanitized preview and GitHub config readiness (without exposing token).
        """
        try:
            data = await request.json()
        except Exception:
            return _error_response("Invalid JSON", status=400, code="invalid_json")

        try:
            preview = build_feedback_preview(data, github_config=GitHubFeedbackConfig.from_env())
            return web.json_response({"success": True, **preview})
        except FeedbackValidationError as e:
            return _error_response(
                str(e),
                status=400,
                code="validation_error",
                extra={"field_errors": getattr(e, "field_errors", {}) or {}},
            )
        except Exception as e:
            logger.error(f"Feedback preview API error: {e}")
            return _error_response(str(e), status=500)

    @server.PromptServer.instance.routes.post("/doctor/feedback/submit")
    async def api_feedback_submit(request):
        """
        F16 submit endpoint (write-sensitive): create GitHub PR with append-only feedback JSON files.
        Admin-gated (loopback convenience mode allowed when no admin token is configured).
        """
        try:
            data = await request.json()
        except Exception:
            return _error_response("Invalid JSON", status=400, code="invalid_json")

        # IMPORTANT: write-sensitive endpoint must remain admin-gated.
        allowed, code, message = validate_admin_request(request, payload=data)
        if not allowed:
            return _admin_denied_response(code, message)

        try:
            result = await submit_feedback(data, github_config=GitHubFeedbackConfig.from_env())

            # Best-effort redacted audit log (server-side only; no secrets recorded)
            try:
                audit = ActionAudit(Path(get_doctor_data_dir()))
                audit.log_action(
                    provider="github",
                    action="feedback_pr_submit",
                    decision="allow",
                    meta={
                        "submission_id": result.get("submission_id"),
                        "repo": ((result.get("github") or {}).get("repo")),
                        "branch": ((result.get("github") or {}).get("branch")),
                        "pr_url": ((result.get("github") or {}).get("pr_url")),
                    },
                )
            except Exception as audit_err:
                logger.warning(f"Feedback audit log failed: {audit_err}")

            return web.json_response({"success": True, **result})
        except FeedbackValidationError as e:
            return _error_response(
                str(e),
                status=400,
                code="validation_error",
                extra={"field_errors": getattr(e, "field_errors", {}) or {}},
            )
        except Exception as e:
            logger.error(f"Feedback submit API error: {e}")
            return _error_response(str(e), status=500)

    @server.PromptServer.instance.routes.get("/doctor/health")
    async def api_health(request):
        """
        Health endpoint for internal diagnostics.
        Returns logger queue stats, SSRF counters, and last analysis state.
        """
        try:
            last_analysis = get_last_analysis()
            analysis_meta = last_analysis.get("analysis_metadata") or {}
            payload = {
                "logger": get_logger_metrics(),
                "dynamic_vram_advisory": get_dynamic_vram_advisory(),
                "ssrf": get_ssrf_metrics(),
                "storage": {
                    "data_dir": get_doctor_data_dir(),
                    "history_size_bytes": getattr(CONFIG, "history_size_bytes", 0),
                    "path_diagnostics": get_path_diagnostics(),
                },
                "outbound_proxy": SessionManager.get_proxy_diagnostics(),
                "last_analysis": {
                    "timestamp": last_analysis.get("timestamp"),
                    "pipeline_status": analysis_meta.get("pipeline_status"),
                },
            }
            return web.json_response({"success": True, "health": payload})
        except Exception as e:
            logger.error(f"Health API error: {str(e)}")
            return _error_response(str(e), status=500)

    # ---- S3: Telemetry API Endpoints ----
    from .telemetry import get_telemetry_store

    # Initialize telemetry with config setting
    _telemetry_store = get_telemetry_store()
    _telemetry_store.enabled = CONFIG.telemetry_enabled

    @server.PromptServer.instance.routes.get("/doctor/telemetry/status")
    async def api_telemetry_status(request):
        """
        Get telemetry status and buffer stats.
        Returns: {"success": bool, "enabled": bool, "stats": {...}}
        """
        try:
            store = get_telemetry_store()
            stats = store.get_stats()
            return web.json_response({
                "success": True,
                "enabled": store.enabled,
                "stats": stats,
                "upload_destination": None,  # Phase 1-3: local only
            })
        except Exception as e:
            logger.error(f"Telemetry status API error: {str(e)}")
            return _error_response(str(e), status=500)

    @server.PromptServer.instance.routes.get("/doctor/telemetry/buffer")
    async def api_telemetry_buffer(request):
        """
        Get buffered telemetry events.
        Returns: {"success": bool, "events": [...]}
        """
        try:
            store = get_telemetry_store()
            events = store.get_buffer()
            return web.json_response({
                "success": True,
                "events": events,
                "count": len(events),
            })
        except Exception as e:
            logger.error(f"Telemetry buffer API error: {str(e)}")
            return _error_response(str(e), status=500)

    @server.PromptServer.instance.routes.post("/doctor/telemetry/track")
    async def api_telemetry_track(request):
        """
        Record a telemetry event.
        Body: {"category": str, "action": str, "label"?: str, "value"?: int}
        Returns: {"success": bool, "message": str}
        """
        try:
            # Security: Same-origin check (reject cross-origin requests)
            origin = request.headers.get("Origin", "")
            host = request.headers.get("Host", "")
            if origin:
                # Extract host from origin (e.g., "http://localhost:8188" -> "localhost:8188")
                from urllib.parse import urlparse
                origin_host = urlparse(origin).netloc
                if origin_host and host and origin_host != host:
                    return _error_response("Cross-origin request rejected", status=403, code="cross_origin_rejected")

            # Security: Check Content-Type
            content_type = request.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                return _error_response("Content-Type must be application/json", status=400, code="invalid_content_type")

            # Security: Payload size limit (1KB)
            content_length = request.content_length or 0
            if content_length > 1024:
                return _error_response("Payload too large", status=413, code="payload_too_large")

            # Parse JSON
            try:
                data = await request.json()
            except Exception:
                return _error_response("Invalid JSON", status=400, code="invalid_json")

            # Security: Reject unexpected fields
            allowed_fields = {"category", "action", "label", "value"}
            if set(data.keys()) - allowed_fields:
                return _error_response("Unexpected fields", status=400, code="unexpected_fields")

            # Track event
            store = get_telemetry_store()
            success, message = store.track(data)

            return web.json_response({"success": success, "message": message})
        except Exception as e:
            logger.error(f"Telemetry track API error: {str(e)}")
            return _error_response(str(e), status=500)

    @server.PromptServer.instance.routes.post("/doctor/telemetry/clear")
    async def api_telemetry_clear(request):
        """
        Clear all buffered telemetry events.
        Returns: {"success": bool, "message": str}
        """
        payload = {}
        try:
            if request.can_read_body:
                payload = await request.json()
        except Exception:
            payload = {}

        # CRITICAL: write-sensitive endpoint must remain admin-gated.
        allowed, code, message = validate_admin_request(request, payload=payload)
        if not allowed:
            return _admin_denied_response(code, message)

        try:
            store = get_telemetry_store()
            store.clear()
            return web.json_response({"success": True, "message": "Buffer cleared"})
        except Exception as e:
            logger.error(f"Telemetry clear API error: {str(e)}")
            return _error_response(str(e), status=500)

    @server.PromptServer.instance.routes.get("/doctor/telemetry/export")
    async def api_telemetry_export(request):
        """
        Export telemetry buffer as downloadable JSON file.
        Returns: JSON file download
        """
        try:
            store = get_telemetry_store()
            json_data = store.export_json()

            return web.Response(
                body=json_data,
                content_type="application/json",
                headers={
                    "Content-Disposition": "attachment; filename=telemetry_export.json"
                }
            )
        except Exception as e:
            logger.error(f"Telemetry export API error: {str(e)}")
            return _error_response(str(e), status=500)

    @server.PromptServer.instance.routes.post("/doctor/telemetry/toggle")
    async def api_telemetry_toggle(request):
        """
        Toggle telemetry enabled/disabled state.
        Body: {"enabled": bool}
        Returns: {"success": bool, "enabled": bool}
        """
        try:
            data = await request.json()
        except Exception:
            return _error_response("Invalid JSON", status=400, code="invalid_json")

        # CRITICAL: write-sensitive endpoint must remain admin-gated.
        allowed, code, message = validate_admin_request(request, payload=data)
        if not allowed:
            return _admin_denied_response(code, message)

        try:
            enabled = data.get("enabled", False)

            store = get_telemetry_store()
            store.enabled = bool(enabled)

            return web.json_response({
                "success": True,
                "enabled": store.enabled,
                "message": "Telemetry enabled" if store.enabled else "Telemetry disabled"
            })
        except Exception as e:
            logger.error(f"Telemetry toggle API error: {str(e)}")
            return _error_response(str(e), status=500)

    # ---- API Routes (R20) ----
    try:
        from .services.routes import (
            api_plugins,
            api_get_job,
            api_resume_job,
            api_cancel_job,
            api_provider_status,
        )

        # Register routes
        server.PromptServer.instance.routes.get("/doctor/plugins")(api_plugins)
        server.PromptServer.instance.routes.get("/doctor/jobs/{job_id}")(api_get_job)
        server.PromptServer.instance.routes.post("/doctor/jobs/{job_id}/resume")(api_resume_job)
        server.PromptServer.instance.routes.post("/doctor/jobs/{job_id}/cancel")(api_cancel_job)
        server.PromptServer.instance.routes.get("/doctor/providers/{provider_id}/status")(api_provider_status)

    except ImportError as e:
        logger.error(f"Failed to import API routes: {e}")




    # ---- F14: Proactive Diagnostics API Endpoints ----
    from .services.diagnostics import (
        get_diagnostics_runner,
        get_diagnostics_store,
        HealthCheckRequest,
        HealthAckRequest,
        IssueStatus,
    )
    from .services.intent import init_intent_system
    from .services.diagnostics.checks import init_checks

    # Initialize checks registry (registers checks with runner)
    try:
        init_checks()
    except Exception as e:
        logger.warning(f"Failed to initialize diagnostics checks: {e}")

    # Initialize intent system (registers scorer with runner)
    try:
        init_intent_system()
    except Exception as e:
        logger.warning(f"Failed to initialize intent system: {e}")

    @server.PromptServer.instance.routes.post("/doctor/health_check")
    async def api_health_check(request):
        """
        F14: Run diagnostics on a workflow snapshot.
        Body: {
            "workflow": {...},
            "scope": "manual|schedule|pre_exec|workflow_change",
            "options": {"include_intent": true, "max_paths": 50}
        }
        Returns: HealthReport
        """
        try:
            data = await request.json()

            # Parse request
            check_request = HealthCheckRequest.from_dict(data)

            # Run diagnostics
            runner = get_diagnostics_runner()
            report = await runner.run(check_request)

            # Save to history
            store = get_diagnostics_store()
            store.save_report(report)

            return web.json_response({
                "success": True,
                "report": report.to_dict(),
            })
        except Exception as e:
            logger.error(f"Health check API error: {str(e)}")
            return _error_response(str(e), status=500)

    @server.PromptServer.instance.routes.get("/doctor/health_report")
    async def api_health_report(request):
        """
        F14: Fetch last computed health report (cached).
        Returns: HealthReport or null

        Fallback: If runner has no in-memory report, returns latest from store.
        """
        try:
            runner = get_diagnostics_runner()
            report = runner.get_last_report()

            if report:
                return web.json_response({
                    "success": True,
                    "report": report.to_dict(),
                })

            # Fallback: Try to get latest from store (survives restart)
            store = get_diagnostics_store()
            history = store.get_history(limit=1, offset=0)
            if history:
                report_id = history[0].get("report_id")
                if report_id:
                    stored_report = store.get_report(report_id)
                    if stored_report:
                        return web.json_response({
                            "success": True,
                            "report": stored_report,
                            "source": "history",  # Indicate this came from store
                        })

            return web.json_response({
                "success": True,
                "report": None,
                "message": "No report available",
            })
        except Exception as e:
            logger.error(f"Health report API error: {str(e)}")
            return _error_response(str(e), status=500)

    @server.PromptServer.instance.routes.get("/doctor/health_history")
    async def api_health_history(request):
        """
        F14: Fetch recent health report metadata.
        Query params: limit (default 50), offset (default 0)
        Returns: List of report metadata (no heavy payload)
        """
        try:
            limit = int(request.query.get("limit", "50"))
            offset = int(request.query.get("offset", "0"))

            # Clamp values
            limit = max(1, min(100, limit))
            offset = max(0, offset)

            store = get_diagnostics_store()
            history = store.get_history(limit=limit, offset=offset)

            return web.json_response({
                "success": True,
                "history": history,
                "count": len(history),
            })
        except Exception as e:
            logger.error(f"Health history API error: {str(e)}")
            return _error_response(str(e), status=500)

    @server.PromptServer.instance.routes.post("/doctor/health_ack")
    async def api_health_ack(request):
        """
        F14: Acknowledge/ignore/resolve an issue.
        Body: {"report_id": "...", "issue_id": "...", "status": "acknowledged|ignored|resolved"}
        Returns: {"success": bool}
        """
        try:
            data = await request.json()
        except Exception:
            return _error_response("Invalid JSON", status=400, code="invalid_json")

        # CRITICAL: write-sensitive endpoint must remain admin-gated.
        allowed, code, message = validate_admin_request(request, payload=data)
        if not allowed:
            return _admin_denied_response(code, message)

        try:
            ack_request = HealthAckRequest.from_dict(data)

            if not ack_request.report_id or not ack_request.issue_id:
                return _error_response(
                    "Missing report_id or issue_id",
                    status=400,
                    code="missing_issue_reference",
                )

            store = get_diagnostics_store()
            updated = store.update_issue_status(
                ack_request.report_id,
                ack_request.issue_id,
                ack_request.status,
            )

            if updated:
                return web.json_response({
                    "success": True,
                    "message": f"Issue status updated to {ack_request.status.value}",
                })
            else:
                return _error_response("Issue not found", status=404, code="not_found")
        except Exception as e:
            logger.error(f"Health ack API error: {str(e)}")
            return _error_response(str(e), status=500)

    _print_registered_routes(_startup_print)

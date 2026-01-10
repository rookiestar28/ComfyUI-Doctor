"""
LLM Client with retry logic, exponential backoff, and safety guards.

R6 Implementation: Network retry logic with exponential backoff.

Integrates with:
- outbound.py (SSRF protection, payload sanitization)
- session_manager.py (shared session, rate/concurrency limits)

IMPORTANT SAFETY NOTES:
- POST requests may cause duplicate charges if retried incorrectly
- Streaming requests should NOT be retried after connection established
- All requests use allow_redirects=False (SSRF protection)
"""

import asyncio
import aiohttp
import uuid
import time
import random
import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    
    # Retry limits
    max_retries: int = 2  # Conservative default
    
    # Timing
    base_delay: float = 1.0           # Initial delay (seconds)
    max_delay: float = 30.0           # Cap on delay
    exponential_base: float = 2.0     # Backoff multiplier
    
    # Timeouts
    request_timeout_seconds: float = 60.0   # Per-attempt timeout
    total_timeout_seconds: float = 180.0    # Entire operation timeout
    
    # Retryable conditions
    retryable_network_errors: bool = True   # ClientError (timeout, refused)
    retry_on_429: bool = True               # Rate limit (with Retry-After)
    retry_on_5xx: bool = False              # Disabled by default (risk of dupe)
    max_5xx_retries: int = 1                # If enabled, limit to 1
    retryable_5xx_codes: Tuple[int, ...] = (502, 503, 504)  # Exclude 500
    
    # Idempotency (OpenAI standard)
    add_idempotency_key: bool = True
    idempotency_header: str = "Idempotency-Key"


@dataclass
class RetryResult:
    """Result of a retry-aware request."""
    response: Optional[aiohttp.ClientResponse]
    success: bool
    attempts: int
    total_time: float
    error: Optional[str] = None
    idempotency_key: Optional[str] = None


def _safe_release(response: aiohttp.ClientResponse) -> None:
    """
    Safely release response resources.
    
    Note: response.close() is synchronous in aiohttp.
    This prevents connection pool leaks when retrying.
    """
    try:
        response.close()
    except Exception:
        pass


def _get_retry_after(
    response: aiohttp.ClientResponse,
    config: RetryConfig,
    attempt: int
) -> float:
    """Parse Retry-After header or calculate backoff."""
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(float(retry_after), config.max_delay)
        except ValueError:
            pass
    return _calculate_backoff(attempt, config)


def _calculate_backoff(attempt: int, config: RetryConfig) -> float:
    """Calculate exponential backoff with jitter."""
    delay = config.base_delay * (config.exponential_base ** (attempt - 1))
    jitter = random.uniform(0, delay * 0.1)  # 10% jitter
    return min(delay + jitter, config.max_delay)


async def llm_request_with_retry(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    *,
    json: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    config: Optional[RetryConfig] = None,
    is_streaming: bool = False,
) -> RetryResult:
    """
    Make HTTP request with safe retry logic.
    
    Args:
        session: aiohttp ClientSession to use
        method: HTTP method (GET, POST, etc.)
        url: Target URL
        json: JSON payload (optional)
        headers: HTTP headers (optional)
        config: Retry configuration (optional, uses defaults)
        is_streaming: If True, marks this as a streaming request
    
    Returns:
        RetryResult with response, success status, and metadata
    
    IMPORTANT:
    - For streaming: retries are DISABLED after connection established
    - Caller must use `async with result.response:` for proper cleanup
    - All requests use allow_redirects=False (SSRF protection)
    
    Example:
        result = await llm_request_with_retry(session, "POST", url, json=payload)
        if result.success:
            async with result.response as resp:
                data = await resp.json()
    """
    config = config or RetryConfig()
    headers = dict(headers) if headers else {}
    
    # Add idempotency key for POST requests
    idempotency_key: Optional[str] = None
    if config.add_idempotency_key and method.upper() == "POST":
        idempotency_key = str(uuid.uuid4())
        headers[config.idempotency_header] = idempotency_key
        logger.debug(f"Added idempotency key: {idempotency_key}")
    
    start_time = time.monotonic()
    attempts = 0
    last_error: Optional[str] = None
    response: Optional[aiohttp.ClientResponse] = None
    
    while attempts <= config.max_retries:
        # Check total timeout budget
        elapsed = time.monotonic() - start_time
        if elapsed >= config.total_timeout_seconds:
            logger.warning(f"Total timeout exceeded ({config.total_timeout_seconds}s)")
            return RetryResult(
                response=None,
                success=False,
                attempts=attempts,
                total_time=elapsed,
                error=f"Total timeout exceeded ({config.total_timeout_seconds}s)",
                idempotency_key=idempotency_key,
            )
        
        attempts += 1
        remaining_time = config.total_timeout_seconds - elapsed
        per_request_timeout = min(config.request_timeout_seconds, remaining_time)
        
        try:
            timeout = aiohttp.ClientTimeout(total=per_request_timeout)
            response = await session.request(
                method,
                url,
                json=json,
                headers=headers,
                allow_redirects=False,  # SSRF protection (required)
                timeout=timeout,
            )
            
            # === Success path (2xx, 3xx) ===
            if response.status < 400:
                logger.debug(f"Request succeeded on attempt {attempts}")
                return RetryResult(
                    response=response,
                    success=True,
                    attempts=attempts,
                    total_time=time.monotonic() - start_time,
                    idempotency_key=idempotency_key,
                )
            
            # === 429 Rate Limit ===
            if response.status == 429 and config.retry_on_429:
                delay = _get_retry_after(response, config, attempts)
                _safe_release(response)
                if attempts <= config.max_retries:
                    logger.warning(
                        f"429 Rate Limited, waiting {delay:.1f}s "
                        f"(attempt {attempts}/{config.max_retries + 1})"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    return RetryResult(
                        response=None,
                        success=False,
                        attempts=attempts,
                        total_time=time.monotonic() - start_time,
                        error="Rate limit exceeded after max retries",
                        idempotency_key=idempotency_key,
                    )
            
            # === 5xx Server Error ===
            if response.status in config.retryable_5xx_codes and config.retry_on_5xx:
                if attempts <= config.max_5xx_retries:
                    delay = _calculate_backoff(attempts, config)
                    _safe_release(response)
                    logger.warning(
                        f"{response.status} Server Error, retry in {delay:.1f}s "
                        f"(attempt {attempts}/{config.max_5xx_retries + 1})"
                    )
                    await asyncio.sleep(delay)
                    continue
            
            # === Non-retryable status (4xx except 429, 500, or exhausted retries) ===
            logger.warning(f"Non-retryable status {response.status}")
            return RetryResult(
                response=response,
                success=False,
                attempts=attempts,
                total_time=time.monotonic() - start_time,
                error=f"HTTP {response.status}",
                idempotency_key=idempotency_key,
            )
            
        except asyncio.TimeoutError:
            last_error = f"Request timeout ({per_request_timeout:.1f}s)"
            logger.warning(f"Timeout on attempt {attempts}")
            if config.retryable_network_errors and attempts <= config.max_retries:
                delay = _calculate_backoff(attempts, config)
                logger.info(f"Retrying in {delay:.1f}s")
                await asyncio.sleep(delay)
                continue
            break
            
        except aiohttp.ClientError as e:
            last_error = str(e)
            logger.warning(f"Network error on attempt {attempts}: {e}")
            if config.retryable_network_errors and attempts <= config.max_retries:
                delay = _calculate_backoff(attempts, config)
                logger.info(f"Retrying in {delay:.1f}s")
                await asyncio.sleep(delay)
                continue
            break
    
    # Exhausted all retries
    logger.error(f"Request failed after {attempts} attempts: {last_error}")
    return RetryResult(
        response=response,
        success=False,
        attempts=attempts,
        total_time=time.monotonic() - start_time,
        error=last_error,
        idempotency_key=idempotency_key,
    )


# Convenience function for non-streaming POST requests
async def llm_post_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    *,
    json: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    config: Optional[RetryConfig] = None,
) -> RetryResult:
    """
    Convenience wrapper for POST requests with retry.
    
    See llm_request_with_retry for full documentation.
    """
    return await llm_request_with_retry(
        session, "POST", url,
        json=json, headers=headers, config=config, is_streaming=False
    )

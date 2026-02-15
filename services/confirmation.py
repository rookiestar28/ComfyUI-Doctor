"""
S9: Confirmation Token Service.

Manages short-lived, single-use tokens for sensitive actions.
Prevents replay attacks and ensures user intent for high-risk operations.
"""

import logging
import time
import uuid
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class ConfirmationTokenService:
    """
    Manages transient tokens required for sensitive operations (e.g., submit/upload).
    Tokens are single-use (`validate_and_consume`) and have a short TTL.
    """
    
    # Token -> (expiry_timestamp, metadata_string)
    _tokens: Dict[str, Tuple[float, str]] = {}
    TTL_SECONDS = 300  # 5 minutes

    @classmethod
    def issue_token(cls, metadata: str = "") -> str:
        """
        Issue a new token valid for TTL_SECONDS.
        Metadata is optional context (e.g., 'upload-dataset-v1').
        """
        token = str(uuid.uuid4())
        expiry = time.time() + cls.TTL_SECONDS
        cls._tokens[token] = (expiry, metadata)
        return token

    @classmethod
    def validate_and_consume(cls, token: str) -> bool:
        """
        Consumes a token. Returns True if valid and not expired.
        This is a destruct-on-read operation.
        """
        if not token or token not in cls._tokens:
            return False
            
        expiry, meta = cls._tokens[token]
        
        # ALWAYS remove token to prevent replay, regardless of expiry status
        del cls._tokens[token]
        
        if time.time() > expiry:
            logger.warning(f"Confirmation token expired (meta: {meta})")
            return False
            
        return True
        
    @classmethod
    def cleanup(cls) -> int:
        """
        Remove expired tokens to prevent memory leaks.
        Returns count of removed items.
        """
        now = time.time()
        expired = [t for t, (exp, _) in cls._tokens.items() if now > exp]
        for t in expired:
            del cls._tokens[t]
        return len(expired)

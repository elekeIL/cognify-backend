"""
Simple In-Memory Rate Limiter for Password Reset Endpoints.

Uses a sliding window approach to limit requests per IP and per email.
For production with multiple instances, consider Redis-based rate limiting.
"""

import time
import logging
from collections import defaultdict
from typing import Dict, List, Tuple
from dataclasses import dataclass
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    max_requests: int  # Maximum requests allowed
    window_seconds: int  # Time window in seconds


class RateLimiter:
    """
    Thread-safe in-memory rate limiter using sliding window.

    For production with multiple backend instances, replace with Redis.
    """

    def __init__(self):
        # Store request timestamps per key
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = Lock()

        # Configuration for different limit types
        self.configs = {
            # Password reset: 5 requests per 15 minutes per IP
            "password_reset_ip": RateLimitConfig(max_requests=5, window_seconds=900),
            # Password reset: 3 requests per hour per email
            "password_reset_email": RateLimitConfig(max_requests=3, window_seconds=3600),
            # OTP verification: 10 attempts per 15 minutes per IP
            "otp_verify_ip": RateLimitConfig(max_requests=10, window_seconds=900),
            # OTP verification: 5 attempts per 15 minutes per email
            "otp_verify_email": RateLimitConfig(max_requests=5, window_seconds=900),
        }

    def _cleanup_old_requests(self, key: str, window_seconds: int) -> None:
        """Remove timestamps outside the current window."""
        now = time.time()
        cutoff = now - window_seconds
        self._requests[key] = [ts for ts in self._requests[key] if ts > cutoff]

    def is_allowed(self, limit_type: str, identifier: str) -> Tuple[bool, int]:
        """
        Check if a request is allowed under rate limiting.

        Args:
            limit_type: Type of rate limit (e.g., "password_reset_ip")
            identifier: Unique identifier (IP address, email, etc.)

        Returns:
            Tuple of (is_allowed: bool, retry_after_seconds: int)
        """
        if limit_type not in self.configs:
            logger.warning(f"Unknown rate limit type: {limit_type}")
            return True, 0

        config = self.configs[limit_type]
        key = f"{limit_type}:{identifier}"

        with self._lock:
            now = time.time()

            # Clean up old requests
            self._cleanup_old_requests(key, config.window_seconds)

            # Check current count
            current_count = len(self._requests[key])

            if current_count >= config.max_requests:
                # Calculate retry time
                oldest_request = min(self._requests[key]) if self._requests[key] else now
                retry_after = int(oldest_request + config.window_seconds - now) + 1
                return False, max(retry_after, 1)

            # Record this request
            self._requests[key].append(now)
            return True, 0

    def record_request(self, limit_type: str, identifier: str) -> None:
        """Record a request without checking limits (for tracking only)."""
        if limit_type not in self.configs:
            return

        config = self.configs[limit_type]
        key = f"{limit_type}:{identifier}"

        with self._lock:
            self._cleanup_old_requests(key, config.window_seconds)
            self._requests[key].append(time.time())

    def get_remaining(self, limit_type: str, identifier: str) -> int:
        """Get remaining requests allowed in current window."""
        if limit_type not in self.configs:
            return 999

        config = self.configs[limit_type]
        key = f"{limit_type}:{identifier}"

        with self._lock:
            self._cleanup_old_requests(key, config.window_seconds)
            return max(0, config.max_requests - len(self._requests[key]))

    def reset(self, limit_type: str, identifier: str) -> None:
        """Reset rate limit for a specific key (e.g., after successful verification)."""
        key = f"{limit_type}:{identifier}"
        with self._lock:
            self._requests.pop(key, None)

    def cleanup_all(self) -> int:
        """Remove all expired entries. Call periodically."""
        now = time.time()
        removed = 0

        with self._lock:
            keys_to_remove = []

            for key, timestamps in self._requests.items():
                # Determine window from key prefix
                limit_type = key.split(":")[0]
                if limit_type in self.configs:
                    window = self.configs[limit_type].window_seconds
                    cutoff = now - window

                    # Filter old timestamps
                    new_timestamps = [ts for ts in timestamps if ts > cutoff]
                    if not new_timestamps:
                        keys_to_remove.append(key)
                    else:
                        self._requests[key] = new_timestamps
                        removed += len(timestamps) - len(new_timestamps)

            for key in keys_to_remove:
                del self._requests[key]
                removed += 1

        return removed


# Global rate limiter instance
rate_limiter = RateLimiter()


def get_client_ip(request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check X-Forwarded-For header (set by reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP (client IP)
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct client
    if request.client:
        return request.client.host

    return "unknown"

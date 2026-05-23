"""
Token-bucket rate limiter for external API calls.

Why token-bucket?
-----------------
A token-bucket allows short bursts (up to ``capacity`` calls) while
enforcing a steady-state throughput ceiling of ``rate`` calls per second.
This matches real-world API contracts better than a fixed-window counter,
which can allow 2× the quota right around window boundaries.

Compared to a leaky-bucket (which queues excess requests), this
implementation raises :exc:`RateLimitExceeded` immediately when the bucket
is empty, letting the caller decide whether to retry or degrade gracefully.
The caller (typically :class:`~src.services.ai_service.AIService`) already
has tenacity exponential-backoff configured, so the exception integrates
naturally with the existing retry layer.

Trade-offs
----------
- **asyncio-safe, single-process.** Token refill uses ``asyncio.get_event_loop().time()``
  (monotonic) so it is immune to wall-clock jumps.  Like the cache, it is
  *not* shared across processes — each worker maintains its own bucket.  A
  Redis ``INCR`` / ``EXPIRE`` approach would be needed for multi-process
  coordination, at the cost of a round-trip per call.
- **Not thread-safe.** The bucket is designed for a single asyncio event
  loop.  If you call ``consume()`` from multiple threads, add a
  ``threading.Lock``.  The current codebase is all-asyncio, so this is fine.
- **No queue.** Callers that exceed the rate get an exception rather than
  being silently delayed, keeping latency predictable.

Usage::

    limiter = TokenBucketRateLimiter(rate=5.0, capacity=10)

    async def my_api_call():
        limiter.consume()          # raises RateLimitExceeded if empty
        return await httpx.get(...)

    # Or use the async context manager:
    async with limiter:
        return await httpx.get(...)
"""
from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when the token bucket is empty and a call cannot be admitted."""


class TokenBucketRateLimiter:
    """Asyncio-safe token-bucket rate limiter.

    Parameters
    ----------
    rate:
        Token refill rate in tokens per second.  Fractional values are
        allowed (e.g. ``0.5`` for one call every two seconds).
    capacity:
        Maximum burst size — the bucket is initialised full.  Must be ≥ 1.

    Examples
    --------
    Limit Wikipedia fetches to 3 req/s with a burst of 5::

        _wiki_limiter = TokenBucketRateLimiter(rate=3.0, capacity=5)

    Then in the fetch wrapper::

        _wiki_limiter.consume()  # or: async with _wiki_limiter:
        result = await ai.fetch_wikipedia(query)
    """

    def __init__(self, rate: float, capacity: float) -> None:
        if rate <= 0:
            raise ValueError(f"rate must be positive, got {rate!r}")
        if capacity < 1:
            raise ValueError(f"capacity must be ≥ 1, got {capacity!r}")
        self._rate = rate
        self._capacity = float(capacity)
        self._tokens = float(capacity)   # start full (burst available immediately)
        self._last_refill: float = time.monotonic()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refill(self) -> None:
        """Add tokens for elapsed time since the last call."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        new_tokens = elapsed * self._rate
        self._tokens = min(self._capacity, self._tokens + new_tokens)
        self._last_refill = now

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def consume(self, tokens: float = 1.0) -> None:
        """Consume *tokens* from the bucket, or raise :exc:`RateLimitExceeded`.

        Parameters
        ----------
        tokens:
            Number of tokens to consume (default 1).  Pass a larger value
            for calls that are proportionally more expensive (e.g. large
            batches).

        Raises
        ------
        RateLimitExceeded
            If fewer than *tokens* tokens are currently available.
        """
        self._refill()
        if self._tokens < tokens:
            wait = (tokens - self._tokens) / self._rate
            logger.warning(
                "rate_limit_exceeded",
                extra={
                    "available": round(self._tokens, 2),
                    "requested": tokens,
                    "retry_after_s": round(wait, 3),
                },
            )
            raise RateLimitExceeded(
                f"Token bucket exhausted. "
                f"Available: {self._tokens:.2f}, requested: {tokens}. "
                f"Retry after ≈{wait:.3f}s."
            )
        self._tokens -= tokens
        logger.debug(
            "rate_limit_consumed",
            extra={"remaining": round(self._tokens, 2), "consumed": tokens},
        )

    @property
    def available(self) -> float:
        """Current token count after refilling for elapsed time (read-only)."""
        self._refill()
        return self._tokens

    # Async context-manager convenience ----------------------------------

    async def __aenter__(self) -> "TokenBucketRateLimiter":
        self.consume()
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    # Repr ---------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"TokenBucketRateLimiter("
            f"rate={self._rate}/s, capacity={self._capacity}, "
            f"available≈{self.available:.2f})"
        )


# ---------------------------------------------------------------------------
# Module-level default limiters (conservative defaults — tune via env vars
# or replace with per-caller instances as needed)
# ---------------------------------------------------------------------------

#: Shared limiter for Wikipedia fetches (free, but polite-crawl guidelines
#: suggest ≤ 200 req/s; we stay well under with 10 req/s burst of 20).
wikipedia_limiter = TokenBucketRateLimiter(rate=10.0, capacity=20)

#: arXiv limits unauthenticated clients to ~3 req/s; we use 2 req/s to be safe.
arxiv_limiter = TokenBucketRateLimiter(rate=2.0, capacity=5)

#: Generic web / DuckDuckGo limiter.  DDG is aggressive about rate-limiting;
#: keep at 1 req/s to avoid empty-result responses under burst traffic.
web_limiter = TokenBucketRateLimiter(rate=1.0, capacity=3)


# ---------------------------------------------------------------------------
# LLM tokens-per-minute (TPM) limiter
# ---------------------------------------------------------------------------

class LlmTpmLimiter:
    """Token-aware rate limiter that enforces a tokens-per-minute (TPM) ceiling.

    Unlike :class:`TokenBucketRateLimiter`, which counts *requests*, this
    class counts **LLM prompt + completion tokens** consumed per minute.
    Each :meth:`consume` call takes the actual token count reported by the
    provider and deducts it from the rolling 60-second budget.

    Why TPM instead of RPM?
    -----------------------
    Provider rate-limit contracts (Anthropic, OpenAI, Google) are expressed
    in tokens-per-minute, *not* requests-per-minute.  A single synthesis call
    that produces 800 completion tokens consumes the same quota as eight
    100-token calls.  Request-rate limiting therefore cannot prevent
    ``429 RateLimitError`` responses under heavy load; only TPM tracking can.

    Algorithm
    ---------
    Uses the same sliding token-bucket mechanic as
    :class:`TokenBucketRateLimiter`, but:

    - The bucket capacity is ``tpm_limit`` (tokens, not requests).
    - The refill rate is ``tpm_limit / 60`` tokens per second (i.e. the
      full budget refills after exactly one minute).
    - :meth:`consume` accepts the number of LLM tokens used by one call.

    Parameters
    ----------
    tpm_limit:
        Maximum tokens per minute.  Anthropic claude-sonnet-4 defaults to
        40 000 TPM on the free tier; set higher for paid tiers.
    """

    #: Anthropic claude-sonnet-4 free-tier default (tokens/minute).
    ANTHROPIC_SONNET_FREE_TPM: int = 40_000
    #: OpenAI gpt-4o-mini default (tokens/minute).
    OPENAI_GPT4O_MINI_TPM: int = 200_000
    #: Google Gemini 2.0 Flash default (tokens/minute).
    GOOGLE_GEMINI_FLASH_TPM: int = 1_000_000

    def __init__(self, tpm_limit: int = ANTHROPIC_SONNET_FREE_TPM) -> None:
        if tpm_limit < 1:
            raise ValueError(f"tpm_limit must be ≥ 1, got {tpm_limit!r}")
        self._tpm_limit = float(tpm_limit)
        # Refill rate: full budget recovers in exactly 60 seconds.
        self._rate_per_second: float = self._tpm_limit / 60.0
        self._available: float = self._tpm_limit   # start with full minute budget
        self._last_refill: float = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._available = min(
            self._tpm_limit,
            self._available + elapsed * self._rate_per_second,
        )
        self._last_refill = now

    def consume(self, tokens: int) -> None:
        """Deduct *tokens* (prompt + completion) from the rolling TPM budget.

        Parameters
        ----------
        tokens:
            Total LLM tokens consumed by one call (prompt tokens +
            completion tokens).  Pass ``prompt_tokens + completion_tokens``
            as reported by the provider response.

        Raises
        ------
        RateLimitExceeded
            If the requested token count exceeds the remaining budget.
            The caller's tenacity retry loop will back off and retry.
        """
        if tokens < 1:
            return   # guard against zero/negative from malformed responses
        self._refill()
        if self._available < tokens:
            wait = (tokens - self._available) / self._rate_per_second
            logger.warning(
                "llm_tpm_limit_exceeded",
                extra={
                    "available_tokens": round(self._available),
                    "requested_tokens": tokens,
                    "retry_after_s": round(wait, 1),
                    "tpm_limit": int(self._tpm_limit),
                },
            )
            raise RateLimitExceeded(
                f"LLM TPM budget exhausted. "
                f"Available: {self._available:.0f} tokens, requested: {tokens}. "
                f"Retry after ≈{wait:.1f}s."
            )
        self._available -= tokens
        logger.debug(
            "llm_tpm_consumed",
            extra={
                "consumed": tokens,
                "remaining": round(self._available),
                "tpm_limit": int(self._tpm_limit),
            },
        )

    @property
    def available_tokens(self) -> float:
        """Remaining token budget after refilling for elapsed time (read-only)."""
        self._refill()
        return self._available

    def __repr__(self) -> str:
        return (
            f"LlmTpmLimiter("
            f"tpm_limit={int(self._tpm_limit)}, "
            f"available≈{self.available_tokens:.0f})"
        )


#: Module-level LLM TPM limiter.  Defaults to Anthropic claude-sonnet-4
#: free-tier (40 000 TPM).  Override by constructing a new instance with
#: the appropriate limit for your provider and tier, or set the environment
#: variable ``LLM_TPM_LIMIT`` and pass it at construction time.
llm_tpm_limiter = LlmTpmLimiter(tpm_limit=LlmTpmLimiter.ANTHROPIC_SONNET_FREE_TPM)

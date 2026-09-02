import time
from bot.db.sqlite import execute, fetchone
from bot.logs.lazy_logger import lazy_logger


class ScheduleCacheRepository:
    """Repository for managing persistent SQLite TTL cache."""

    async def get_payload(
        self, cache_key: str, allow_expired: bool = False
    ) -> tuple[str, bool] | None:
        """
        Retrieve cached payload and whether it is expired.
        Returns (payload, is_expired) or None if not found (or expired and allow_expired=False).
        """
        try:
            row = await fetchone(
                "SELECT payload, expires_at FROM schedule_cache WHERE cache_key = ?",
                (cache_key,),
            )
            if not row:
                return None

            payload, expires_at = row
            now = time.time()
            is_expired = now > float(expires_at)

            if is_expired and not allow_expired:
                return None

            return payload, is_expired
        except Exception as e:
            lazy_logger.logger.warning(
                f"ScheduleCacheRepository.get_payload failed for '{cache_key}': {e}"
            )
            return None

    async def set_payload(
        self, cache_key: str, payload: str, ttl_seconds: int
    ) -> bool:
        """Save or update cache payload with TTL."""
        try:
            now = time.time()
            expires_at = now + ttl_seconds
            await execute(
                """
                INSERT INTO schedule_cache (cache_key, payload, updated_at, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at
                """,
                (cache_key, payload, now, expires_at),
            )
            return True
        except Exception as e:
            lazy_logger.logger.warning(
                f"ScheduleCacheRepository.set_payload failed for '{cache_key}': {e}"
            )
            return False

    async def delete_expired(self) -> int:
        """Purge expired cache entries."""
        try:
            now = time.time()
            # Fetch count before deleting
            row = await fetchone(
                "SELECT COUNT(*) FROM schedule_cache WHERE expires_at < ?",
                (now,),
            )
            count = row[0] if row else 0
            if count > 0:
                await execute(
                    "DELETE FROM schedule_cache WHERE expires_at < ?",
                    (now,),
                )
            return count
        except Exception as e:
            lazy_logger.logger.warning(
                f"ScheduleCacheRepository.delete_expired failed: {e}"
            )
            return 0

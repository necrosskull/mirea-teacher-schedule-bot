import asyncio
from datetime import date

import httpx

from bot.config import settings
from bot.fetch.models import (
    ScheduleData,
    ScheduleTargetType,
    SearchItem,
)
from bot.logs.lazy_logger import lazy_logger


def _iso(value: date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


class ScheduleApiClient:
    """Client for the Supabase schedule backend (schedule RPCs of university-app).

    Uses PostgREST RPC endpoints:

    * ``search_schedule_targets(p_target_type, p_query, p_organization_id, p_limit)``
    * ``get_schedule_for_entity(p_entity_type, p_entity, p_date_from, p_date_to, p_organization_id)``

    The old ``app-api.mirea.ninja`` host is no longer used.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        organization_id: str | None = None,
        timeout: float = 10.0,
        search_limit: int | None = None,
    ):
        self.base_url = (
            base_url if base_url is not None else settings.supabase_url or ""
        ).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.supabase_key or ""
        self.organization_id = organization_id or settings.organization_id
        self.timeout = timeout
        self.search_limit = (
            search_limit if search_limit is not None else settings.schedule_search_limit
        )

    @property
    def _rpc_url(self) -> str:
        return f"{self.base_url}/rest/v1/rpc"

    @property
    def configured(self) -> bool:
        """True when both Supabase URL and key are available."""
        return bool(self.base_url and self.api_key)

    def _log_missing_config(self) -> None:
        lazy_logger.logger.error(
            "SUPABASE_URL and SUPABASE_KEY are not set. Add them to .env "
            "(see .env.example) - schedule requests are disabled."
        )

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _rpc(
        self, client: httpx.AsyncClient, function: str, payload: dict
    ) -> list | dict:
        response = await client.post(
            f"{self._rpc_url}/{function}", headers=self._headers, json=payload
        )
        response.raise_for_status()
        return response.json()

    def _to_search_item(self, target_type: ScheduleTargetType, raw: dict) -> SearchItem | None:
        external_id = raw.get("external_id")
        try:
            uid = int(str(external_id).strip())
        except (TypeError, ValueError):
            lazy_logger.logger.warning(
                f"ScheduleApiClient.search skipped {target_type.value} item "
                f"with non-numeric external_id={external_id!r}"
            )
            return None

        name = raw.get("target_title") or raw.get("full_title") or ""
        return SearchItem(type=target_type.value, uid=uid, name=name)

    async def search(self, query: str) -> list[SearchItem] | None:
        if not self.configured:
            self._log_missing_config()
            return None

        payload_base = {
            "p_query": query,
            "p_organization_id": self.organization_id,
            "p_limit": self.search_limit,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = [
                self._rpc(
                    client,
                    "search_schedule_targets",
                    {"p_target_type": target.value, **payload_base},
                )
                for target in ScheduleTargetType
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

        items: list[SearchItem] = []
        errors: list[Exception] = []
        for target, response in zip(ScheduleTargetType, responses):
            if isinstance(response, Exception):
                errors.append(response)
                continue
            if not isinstance(response, list):
                continue
            for raw in response:
                item = self._to_search_item(target, raw)
                if item is not None:
                    items.append(item)

        if errors:
            lazy_logger.logger.warning(
                f"ScheduleApiClient.search partially failed for query='{query}': "
                f"{[str(error) for error in errors]}"
            )
            if not items:
                return None

        # Keep the result stable and free of duplicates (same entity can be
        # matched by more than one target query).
        unique: dict[tuple[str, int], SearchItem] = {}
        for item in items:
            unique.setdefault((item.type, item.uid), item)
        return list(unique.values())

    async def get_schedule(
        self,
        target: SearchItem,
        date_from: date | str | None = None,
        date_to: date | str | None = None,
    ) -> ScheduleData | None:
        if not self.configured:
            self._log_missing_config()
            return None

        payload = {
            "p_entity_type": target.type,
            "p_entity": str(target.uid),
            "p_organization_id": self.organization_id,
        }
        if date_from is not None:
            payload["p_date_from"] = _iso(date_from)
        if date_to is not None:
            payload["p_date_to"] = _iso(date_to)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                json_response = await self._rpc(
                    client, "get_schedule_for_entity", payload
                )
            except Exception as e:
                lazy_logger.logger.warning(
                    f"ScheduleApiClient.get_schedule failed for "
                    f"{target.type}:{target.uid}: {e}"
                )
                return None

        if not isinstance(json_response, list):
            lazy_logger.logger.warning(
                f"ScheduleApiClient.get_schedule unexpected response for "
                f"{target.type}:{target.uid}: {type(json_response).__name__}"
            )
            return None

        try:
            return ScheduleData.from_wire(json_response)
        except Exception as e:
            lazy_logger.logger.warning(
                f"ScheduleApiClient.get_schedule could not parse response for "
                f"{target.type}:{target.uid}: {e}"
            )
            return None

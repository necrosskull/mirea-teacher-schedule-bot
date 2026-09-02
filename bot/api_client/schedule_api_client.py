import asyncio

import httpx

from bot.config import settings
from bot.fetch.models import ScheduleData, ScheduleEndpoints, SearchItem, SearchResults
from bot.logs.lazy_logger import lazy_logger


class ScheduleApiClient:
    def __init__(self, base_url: str | None = None, timeout: float = 10.0):
        self.base_url = (base_url or settings.api_url or "").rstrip("/")
        self.timeout = timeout

    async def search(self, query: str) -> list[SearchItem] | None:
        search_endpoint = f"{self.base_url}/api/v1/schedule/search/"

        results = {}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = []

            for search_type in ScheduleEndpoints:
                url = search_endpoint + search_type.value
                params = {"query": query}
                tasks.append(client.get(url, params=params))

            try:
                responses = await asyncio.gather(*tasks)

                for search_type, response in zip(
                    ScheduleEndpoints,
                    responses,
                ):
                    st_val = search_type.value
                    response.raise_for_status()
                    json_response = response.json()

                    results[st_val] = []

                    if "results" in json_response and len(json_response["results"]) > 0:
                        for item in json_response.get("results", []):
                            item["type"] = st_val
                            if st_val == "classrooms":
                                campus_short_name = item.get("campus", {}).get(
                                    "short_name", ""
                                )
                                if campus_short_name:
                                    item["name"] = f"{item['name']} ({campus_short_name})"
                                else:
                                    item["name"] = item["name"]

                            results[st_val].append(SearchItem(**item))

                search_results = SearchResults(**results)
            except Exception as e:
                lazy_logger.logger.warning(f"ScheduleApiClient.search failed for query='{query}': {e}")
                return None

        return [item for _, items in search_results if items for item in items]

    async def get_schedule(self, target: SearchItem) -> ScheduleData | None:
        url = f"{self.base_url}/api/v1/schedule/{target.type}/{target.uid}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                json_response = response.json()
            except Exception as e:
                lazy_logger.logger.warning(f"ScheduleApiClient.get_schedule failed for {target.type}:{target.uid}: {e}")
                return None

            return ScheduleData(**json_response)


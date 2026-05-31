import asyncio

import httpx

from bot.config import settings
from bot.fetch.models import ScheduleData, ScheduleEndpoints, SearchItem, SearchResults


class ScheduleApiClient:
    async def search(self, query: str) -> list[SearchItem] | None:
        base_url = f"{settings.api_url}/api/v1/schedule/search/"

        results = {}
        async with httpx.AsyncClient() as client:
            tasks = []

            for search_type in ScheduleEndpoints:
                url = base_url + search_type.value
                params = {"query": query}

                task = client.get(url, params=params)
                tasks.append(task)

            try:
                responses = await asyncio.gather(*tasks)

                for search_type, response in zip(
                    ScheduleEndpoints,
                    responses,
                ):
                    search_type = search_type.value
                    response.raise_for_status()
                    json_response = response.json()

                    results[search_type] = []

                    if "results" in json_response and len(json_response["results"]) > 0:
                        for item in json_response.get("results", []):
                            item["type"] = search_type
                            if search_type == "classrooms":
                                campus_short_name = item.get("campus", {}).get(
                                    "short_name", ""
                                )
                                if campus_short_name:
                                    item["name"] = f"{item['name']} ({campus_short_name})"
                                else:
                                    item["name"] = item["name"]

                            results[search_type].append(SearchItem(**item))

                search_results = SearchResults(**results)
            except Exception:
                return None

        return [item for _, items in search_results for item in items]

    async def get_schedule(self, target: SearchItem) -> ScheduleData | None:
        base_url = f"{settings.api_url}/api/v1/schedule/{target.type}/{target.uid}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(base_url)
                response.raise_for_status()
                json_response = response.json()

            except Exception:
                return None

            return ScheduleData(**json_response)

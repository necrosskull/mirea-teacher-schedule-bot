from bot.api_client import ScheduleApiClient
from bot.fetch.models import SearchItem


async def search_schedule(query: str) -> list[SearchItem] | None:
    return await ScheduleApiClient().search(query)


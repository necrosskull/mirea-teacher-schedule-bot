import pytest
from dishka import AsyncContainer

from bot.api_client import ScheduleApiClient
from bot.di import create_container
from bot.repository import ScheduleCacheRepository, UserRepository, UserStateRepository
from bot.service import NotificationService, ScheduleService, StateService, UserService


@pytest.mark.asyncio
async def test_di_container_resolution():
    container: AsyncContainer = create_container()
    try:
        async with container() as request_container:
            api_client = await request_container.get(ScheduleApiClient)
            user_repo = await request_container.get(UserRepository)
            state_repo = await request_container.get(UserStateRepository)
            cache_repo = await request_container.get(ScheduleCacheRepository)
            schedule_svc = await request_container.get(ScheduleService)
            user_svc = await request_container.get(UserService)
            notify_svc = await request_container.get(NotificationService)
            state_svc = await request_container.get(StateService)

            assert isinstance(api_client, ScheduleApiClient)
            assert isinstance(user_repo, UserRepository)
            assert isinstance(state_repo, UserStateRepository)
            assert isinstance(cache_repo, ScheduleCacheRepository)
            assert isinstance(schedule_svc, ScheduleService)
            assert isinstance(user_svc, UserService)
            assert isinstance(notify_svc, NotificationService)
            assert isinstance(state_svc, StateService)

    finally:
        await container.close()

from dishka import Provider, Scope, make_async_container, provide

from bot.api_client import ScheduleApiClient
from bot.repository import ScheduleCacheRepository, UserRepository, UserStateRepository
from bot.service import NotificationService, ScheduleService, StateService, UserService


class AppProvider(Provider):
    @provide(scope=Scope.APP)
    def provide_schedule_api_client(self) -> ScheduleApiClient:
        return ScheduleApiClient()

    @provide(scope=Scope.APP)
    def provide_user_repository(self) -> UserRepository:
        return UserRepository()

    @provide(scope=Scope.APP)
    def provide_user_state_repository(self) -> UserStateRepository:
        return UserStateRepository()

    @provide(scope=Scope.APP)
    def provide_schedule_cache_repository(self) -> ScheduleCacheRepository:
        return ScheduleCacheRepository()

    @provide(scope=Scope.APP)
    def provide_schedule_service(
        self,
        schedule_api_client: ScheduleApiClient,
        schedule_cache_repository: ScheduleCacheRepository,
        user_repository: UserRepository,
    ) -> ScheduleService:
        return ScheduleService(
            schedule_api_client,
            cache_repo=schedule_cache_repository,
            user_repo=user_repository,
        )



    @provide(scope=Scope.APP)
    def provide_user_service(
        self,
        user_repository: UserRepository,
    ) -> UserService:
        return UserService(user_repository)

    @provide(scope=Scope.APP)
    def provide_notification_service(
        self,
        user_repository: UserRepository,
    ) -> NotificationService:
        return NotificationService(user_repository)

    @provide(scope=Scope.APP)
    def provide_state_service(
        self,
        user_state_repository: UserStateRepository,
    ) -> StateService:
        return StateService(user_state_repository)


def create_container():
    return make_async_container(AppProvider())

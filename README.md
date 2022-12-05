# Телеграм бот с расписанием преподователей РТУ МИРЭА
 [![BOT - LINK](https://img.shields.io/static/v1?label=BOT&message=LINK&color=229ed9&style=for-the-badge)](https://t.me/teacherschedulertu_bot)

## О проекте
Проект представляет собой бота для телеграма, который позволяет получать расписание `преподавателей РТУ МИРЭА.`

Проект написан на языке `Python` с использованием библиотеки `python-telegram-bot 13.14.`

Расписание берется через [API Mirea Ninja](https://github.com/mirea-ninja/rtu-mirea-schedule), который предоставляет расписание в формате `JSON.`

Бот находится в стадии активной разработки, поэтому возможны ошибки и недоработки.
***

# Запуск бота

### Локальный запуск

1. Установите все необходимые зависимости, используя Poetry:
```bash
poetry install
```
2. Добавьте файл `.env` в корневую директорию проекта и заполните его по примеру `.env.example`
3. Запустите приложение:
```bash
poetry run python bot/main.py
```

### Запуск с использованием Docker

Чтобы запустить это приложение с помощью docker, для начала вам необходимо собрать локальный образ контейнера:

```bash
docker build -t telegram_bot .
``` 

```bash
docker run -e TELEGRAM_TOKEN=<TELEGRAM_TOKEN> -t telegram_bot
```

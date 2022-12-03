# RU
# МИРЭА телеграм бот расписания
Проект написан на языке `Python` с использованием библиотеки `python-telegram-bot 13.14.`

Расписание берется через [API Mirea Ninja](https://github.com/mirea-ninja/rtu-mirea-schedule), который предоставляет расписание в формате `JSON.`

Бот находится в стадии активной разработки, поэтому возможны ошибки и недоработки.
***
## Установка:
    python -m venv env
    env/Scripts/Activate.ps1
    pip install -r requirements.txt
Создать файл  `config.py` и вставить в него следующий код:

    token = '<Ваш токен>'
***
## Запуск:
    python main.py

# EN
# MIREA schedule telegram bot
schedule gets from [API Mirea Ninja](https://github.com/mirea-ninja/rtu-mirea-schedule), which provides schedule in `JSON` format.

This bot still work in progress, so there may be errors and shortcomings.
***
## Installing:
    python -m venv env
    env/Scripts/Activate.ps1
    pip install -r requirements.txt
Create `config.py` like:
    
    token = '<your token>'
***
## Running:
    python main.py

# MIREA schedule telegram bot
## Installing and running:

    git clone https://github.com/V4kodin/mirea-teacher-schedule-bot
    python -m venv env
    env/Scripts/Activate.ps1
    pip install -r requirements.txt
create config.py like:

<<<<<<< HEAD
    TOKEN = 'your token'
=======
Проект написан на языке `Python` с использованием библиотеки `python-telegram-bot 13.14.`

Расписание берется через [API Mirea Ninja](https://github.com/mirea-ninja/rtu-mirea-schedule), который предоставляет расписание в формате `JSON.`

Бот находится в стадии активной разработки, поэтому возможны ошибки и недоработки.
***
## Установка:
Для работы бота необходимо установить следующие библиотеки:

 * `python-telegram-bot 13.14`
 * `requests`

Или установить их с помощью файла `requirements.txt`

Создать файл  `config.py` и вставить в него следующий код:

    token = 'Ваш токен'
>>>>>>> main

start bot:

    python main.py

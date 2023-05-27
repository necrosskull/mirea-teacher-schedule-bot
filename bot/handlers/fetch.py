import requests


def fetch_schedule_by_name(teacher_name):
    """
    Получение информации о расписании через API Mirea Ninja
    @param teacher_name: Имя преподавателя
    @return: JSON расписание или None если преподаватель не найден
    """

    url = f"https://timetable.mirea.ru/api/teacher/search/{teacher_name}"

    try:
        response = requests.get(url)
        return response.json() if response.status_code == 200 else None

    except requests.RequestException:
        return None


def fetch_room_id_by_name(room_name):
    """
    Получение информации о расписании через API Mirea Ninja
    @param room_name: Номер аудитории
    @return: JSON расписание или None если аудитория не найдена
    """

    url = f"https://timetable.mirea.ru/api/room/search/{room_name}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if len(data) > 0:
                all_rooms = data

                return all_rooms
            else:
                return None
        else:
            return None

    except requests.RequestException:
        return None


def fetch_room_schedule_by_id(room_id):
    """
    Получение информации о расписании через API Mirea Ninja
    @param room_id: id аудитории
    @return: JSON расписание или None если аудитория не найдена
    """

    url = f"https://timetable.mirea.ru/api/schedule/room/{room_id}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if len(data) > 0:
                all_rooms = data

                return all_rooms
            else:
                return None
        else:
            return None

    except requests.RequestException:
        return None

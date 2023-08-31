import requests

from bot.config import api_url


def fetch_schedule_by_name(teacher_name):
    """
    Получение информации о расписании через API Mirea Ninja
    @param teacher_name: Имя преподавателя
    @return: JSON расписание или None если преподаватель не найден
    """

    url = f"{api_url}/api/teachers/search/{teacher_name}"

    try:
        response = requests.get(url, timeout=5)
        return response.json() if response.status_code == 200 else None

    except requests.RequestException:
        return None


def fetch_room_id_by_name(room_name):
    """
    Получение информации о расписании через API Mirea Ninja
    @param room_name: Номер аудитории
    @return: JSON расписание или None если аудитория не найдена
    """

    url = f"{api_url}/api/rooms/search/{room_name}"

    try:
        response = requests.get(url, timeout=5)
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

    url = f"{api_url}/api/lessons/rooms/{room_id}"

    try:
        response = requests.get(url, timeout=5)
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


def fetch_schedule_by_group(group_name):
    """
    Получение информации о расписании через API Mirea Ninja
    @param group_name: Номер группы
    @return: JSON расписание или None если группа не найдена
    """

    url = f"{api_url}/api/groups/name/{group_name}"

    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if len(data) > 0:
                all_groups = data

                return all_groups
            else:
                return None
        else:
            return None

    except requests.RequestException:
        return None

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

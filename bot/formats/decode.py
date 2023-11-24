import requests

import bot.config as config


def decode_teachers(rawNames):
    """
    Декодирует ФИО преподавателей используя API
    :param rawNames: список необработанных ФИО
    """
    if not config.decode_url:
        return rawNames

    decoded_list = []
    for name in rawNames:
        url = f"{config.decode_url}/schedule/api/search?match={name}"
        response = requests.get(
            url,
        )

        if response.status_code == 200:
            resp = response.json()

            if resp:
                if not resp["data"] or len(resp["data"]) > 1:
                    decoded_list.append(name)
                    continue

                full_title = resp["data"][0]["fullTitle"]
                decoded_list.append(full_title)

            else:
                return rawNames

        else:
            return rawNames

    return decoded_list

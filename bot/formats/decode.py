import requests

import bot.config as config


def decode_teachers(rawNames):
    """
    Декодирует ФИО преподавателей используя API CMS
    :param rawNames: список необработанных ФИО
    """
    if not config.cmstoken:
        return rawNames

    headers = {"Authorization": f"Bearer {config.cmstoken}"}
    params = {"rawNames": ",".join(rawNames)}

    response = requests.get(
        "https://cms.mirea.ninja/api/get-full-teacher-name",
        headers=headers,
        params=params,
    )

    if response.status_code == 200:
        data = response.json()

        if data:
            decoded_names = {}

            for names in data:
                if len(names["possibleFullNames"]) == 1:
                    decomposed_name = names["possibleFullNames"][0]
                    name = []

                    if surname := decomposed_name.get("lastName"):
                        name.append(surname)

                    if first_name := decomposed_name.get("firstName"):
                        name.append(first_name)

                    if middle_name := decomposed_name.get("middleName"):
                        name.append(middle_name)

                    name = " ".join(name)
                    raw_name = names["rawName"]
                    decoded_names[raw_name] = name

            # Create a list of decoded names in the same order as raw names
            decoded_list = [
                decoded_names[raw_name] if raw_name in decoded_names else raw_name
                for raw_name in rawNames
            ]

        else:
            decoded_list = rawNames

    else:
        decoded_list = rawNames

    return decoded_list

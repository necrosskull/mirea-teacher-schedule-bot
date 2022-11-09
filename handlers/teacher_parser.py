




def list_of_teachers(map):
    array = []
    for i in map['schedules']:
        if i['lesson']['teachers'] not in array:
            array.append(i['lesson']['teachers'])
        return array

#import json, os
#from pathlib import Path

#возвращает список учителей из словаря api
def list_of_teachers(map):
    array = []
    for i in map['schedules']:
        teachers = i['lesson']['teachers']
        if len(teachers) == 1:
            if teachers[0] not in array:
                array.append(teachers[0])
        elif len(teachers) > 1:
            for j in teachers:
                if j not in array:
                    array.append(j)
    unique(array)
    return array

#проверка на уникальность
def unique(arr):
    N = len(arr)
    for i in range(N - 1):
        for j in range(i + 1, N):
            if arr[i] == arr[j]:
                print("Есть одинаковые")
                quit()


    print("Все элементы уникальны")


#a = os.path.dirname(__file__)
#BaseDir = a[:a.find("\\", -len(os.path.basename(__file__))) + 1]
#BaseDir = "C:/Users/V4kodin/Desktop/GIT/mirea-teacher-schedule-bot/"
#with open(BaseDir + "test.txt", "r", encoding="utf8") as f:
#    map = json.load(f)
#    array = map["schedules"]
#    a = list_of_teachers(map)
#    print(a)
import datetime

SIGN = 0
DATE = 1
INTERVAL = 2

__today_year = datetime.date.today().year
important_days = [
    ["❤️", datetime.date(year=__today_year, month=2, day=14), 2],
    ["❄️", datetime.date(year=__today_year, month=12, day=31), 10],
    ["🎖️", datetime.date(year=__today_year, month=2, day=23), 1],
    ["🌷", datetime.date(year=__today_year, month=3, day=8), 2],
    ["🤡", datetime.date(year=__today_year, month=4, day=1), 2],
    ["⚒️", datetime.date(year=__today_year, month=5, day=1), 1],
    ["🎖️", datetime.date(year=__today_year, month=5, day=9), 2],
]

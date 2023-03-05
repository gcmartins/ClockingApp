import datetime
import pandas as pd
import os.path

filename = 'work_hours.csv'
header = ["Date", "Check In", "Check Out"]


def record_check_in() -> None:
    with open(filename, "a") as f:
        current_time = datetime.datetime.now()
        f.write("{},{},{}\n".format(current_time.date(), current_time.time(), ""))


def record_check_out() -> None:
    with open(filename, "r+") as f:
        lines = f.readlines()
        if len(lines) == 0:
            return
        last_line = lines[-1].rstrip('\n').split(',')
        if len(last_line) == 3 and last_line[2] == '':
            last_line[2] = str(datetime.datetime.now().time())
            lines[-1] = ','.join(last_line) + '\n'
            f.seek(0)
            f.writelines(lines)
        else:
            return


def get_today_worked_hours() -> datetime.timedelta:
    df = pd.read_csv(filename, parse_dates=["Check In", "Check Out"])
    today = datetime.date.today()
    today_data = df[df["Date"] == today]
    if len(today_data) == 0:
        return datetime.timedelta(0)
    elif len(today_data) == 1 and pd.isna(today_data["Check Out"].iloc[0]):
        return datetime.timedelta(0)
    else:
        today_data["Duration"] = today_data["Check Out"] - today_data["Check In"]
        todays_hours = today_data["Duration"].sum()
        return todays_hours


def format_timedelta(td: datetime.timedelta) -> str:
    seconds = td.seconds
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)


def warn_if_overtime() -> None:
    todays_hours = get_today_worked_hours()
    if todays_hours >= datetime.timedelta(hours=8):
        print("Warning: You have worked {} today.".format(format_timedelta(todays_hours)))


def main() -> None:
    if not os.path.isfile(filename):
        with open(filename, "w") as f:
            f.write(','.join(header) + '\n')

    print("Welcome to the work hours app.")
    print("Press 'i' to record your check in time.")
    print("Press 'o' to record your check out time.")
    print("Press 'q' to quit the app.")

    while True:
        choice = input("Enter your choice: ")
        if choice == "i":
            record_check_in()
        elif choice == "o":
            record_check_out()
        elif choice == "q":
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")
            continue

        todays_hours = get_today_worked_hours()
        print("Total worked hours today: {}".format(format_timedelta(todays_hours)))
        warn_if_overtime()


if __name__ == "__main__":
    main()

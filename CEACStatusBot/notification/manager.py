import json
import os
import datetime

import pytz

from CEACStatusBot.captcha import CaptchaHandle, OnnxCaptchaHandle
from CEACStatusBot.request import query_status

from .handle import NotificationHandle

DEFAULT_ACTIVE_HOURS = "00:00-23:59"


class NotificationManager:
    def __init__(
        self,
        location: str,
        number: str,
        passport_number: str,
        surname: str,
        captchaHandle: CaptchaHandle = OnnxCaptchaHandle("captcha.onnx"),
    ) -> None:
        self.__handleList = []
        self.__location = location
        self.__number = number
        self.__captchaHandle = captchaHandle
        self.__passport_number = passport_number
        self.__surname = surname
        self.__status_file = "status_record.json"

    def _get_hour_range(self) -> list:
        active_hours = os.getenv("ACTIVE_HOURS")
        if active_hours is None or active_hours.strip() == "":
            active_hours = DEFAULT_ACTIVE_HOURS
        parts = active_hours.split("-")
        if len(parts) != 2:
            print(f"Invalid ACTIVE_HOURS format '{active_hours}', expected 'HH:MM-HH:MM'. Using default: {DEFAULT_ACTIVE_HOURS}")
            active_hours = DEFAULT_ACTIVE_HOURS
            parts = active_hours.split("-")
        start_str, end_str = parts
        start = datetime.datetime.strptime(start_str.strip(), "%H:%M").time()
        end = datetime.datetime.strptime(end_str.strip(), "%H:%M").time()
        if start > end:
            raise ValueError("Start time must be before end time, got start: {start}, end: {end}")
        return start, end

    def addHandle(self, notificationHandle: NotificationHandle) -> None:
        self.__handleList.append(notificationHandle)

    def test(self) -> None:
        """Send a test notification to verify all channels are working."""
        if not self.__handleList:
            print("No notification channels configured.")
            return

        test_result = {
            "success": True,
            "time": str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "visa_type": "TEST",
            "status": "Test Notification",
            "case_created": "N/A",
            "case_last_updated": "N/A",
            "description": "This is a test notification to verify your notification channels are working correctly.",
            "application_num": self.__number,
            "application_num_origin": self.__number,
        }

        for handle in self.__handleList:
            handle.send(test_result)

    def send(self) -> None:
        res = query_status(
            self.__location,
            self.__number,
            self.__passport_number,
            self.__surname,
            self.__captchaHandle,
        )
        if not res.get("success"):
            error_msg = res.get("error", "Unknown error")
            print(f"Failed to query CEAC status: {error_msg}")
            return
        current_status = res["status"]
        current_last_updated = res["case_last_updated"]
        print(f"Current status: {current_status} - Last updated: {current_last_updated}")
        # Load the previous statuses from the file
        statuses = self.__load_statuses()

        # Check if the current status is different from the last recorded status
        if not statuses or current_status != statuses[-1].get("status", None) or current_last_updated != statuses[-1].get("last_updated", None):
            self.__save_current_status(current_status, current_last_updated)
            self.__send_notifications(res)
        else:
            print("Status unchanged. No notification sent.")

    def __load_statuses(self) -> list:
        if os.path.exists(self.__status_file):
            with open(self.__status_file, "r") as file:
                return json.load(file).get("statuses", [])
        return []

    def __save_current_status(self, status: str, last_updated: str) -> None:
        statuses = self.__load_statuses()
        statuses.append({
            "status": status,
            "last_updated": last_updated,
            "date": datetime.datetime.now().isoformat()
        })

        with open(self.__status_file, "w") as file:
            json.dump({"statuses": statuses}, file)

    def __send_notifications(self, res: dict) -> None:
        if res["status"] == "Refused":
            try:
                TIMEZONE = os.environ["TIMEZONE"]
                localTimeZone = pytz.timezone(TIMEZONE)
                localTime = datetime.datetime.now(localTimeZone)
            except pytz.exceptions.UnknownTimeZoneError:
                print("UNKNOWN TIMEZONE Error, use default")
                localTime = datetime.datetime.now()
            except KeyError:
                print("TIMEZONE Error")
                localTime = datetime.datetime.now()

            active_hour_start, active_hour_end = self._get_hour_range()
            start_dt = datetime.datetime.combine(localTime.date(), active_hour_start, tzinfo=localTimeZone)
            end_dt = datetime.datetime.combine(localTime.date(), active_hour_end, tzinfo=localTimeZone)
            if not (start_dt <= localTime <= end_dt):
                print(
                    f"Outside active hours {os.getenv('ACTIVE_HOURS', DEFAULT_ACTIVE_HOURS)}. "
                    "No notification sent for Refused status."
                )
                return

        for notificationHandle in self.__handleList:
            notificationHandle.send(res)

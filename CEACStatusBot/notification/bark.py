import requests
import json
from .handle import NotificationHandle


class BarkNotificationHandle(NotificationHandle):
    def __init__(self, device_key: str, server_url: str = "https://api.day.app") -> None:
        super().__init__()
        self.__device_key = device_key
        self.__server_url = server_url.rstrip("/")
        self.__api_url = f"{self.__server_url}/{self.__device_key}"

    def send(self, result):
        title = f"[CEACStatusBot] {result['application_num_origin']}: {result['status']}"
        body = json.dumps(result, indent=2)

        payload = {
            "title": title,
            "body": body,
            "group": "CEACStatusBot",
        }

        response = requests.post(self.__api_url, json=payload)

        if response.status_code == 200:
            resp_data = response.json()
            if resp_data.get("code") == 200:
                print("Bark message sent successfully")
            else:
                print(f"Failed to send Bark message: {resp_data.get('message')}")
        else:
            print(f"Failed to send Bark message: {response.text}")

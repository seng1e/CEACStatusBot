import argparse
import json
import os
import subprocess

from dotenv import load_dotenv

from CEACStatusBot import (
    BarkNotificationHandle,
    EmailNotificationHandle,
    ManualCaptchaHandle,
    NotificationManager,
    TelegramNotificationHandle,
)

# --- Load .env if present, else fallback to system env ---
if os.path.exists(".env"):
    load_dotenv(dotenv_path=".env")


def download_artifact():
    """Download status artifact from GitHub Actions (only works in CI environment)."""
    if "GITHUB_REPOSITORY" not in os.environ:
        # Not in GitHub Actions, create empty status file
        with open("status_record.json", "w") as file:
            json.dump({"statuses": []}, file)
        return

    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/artifacts"],
            capture_output=True,
            text=True,
        )
        artifacts = json.loads(result.stdout)
        artifact_exists = any(artifact["name"] == "status-artifact" for artifact in artifacts["artifacts"])

        if artifact_exists:
            subprocess.run(["gh", "run", "download", "--name", "status-artifact"], check=True)
        else:
            with open("status_record.json", "w") as file:
                json.dump({"statuses": []}, file)
    except Exception as e:
        print(f"Error downloading artifact: {e}")
        with open("status_record.json", "w") as file:
            json.dump({"statuses": []}, file)


def setup_notification_channels(notification_manager):
    """Setup notification channels and return list of enabled channel names."""
    enabled_channels = []

    # Email
    from_email = os.getenv("FROM")
    to_email = os.getenv("TO")
    password = os.getenv("PASSWORD")
    smtp = os.getenv("SMTP", "")

    if from_email and to_email and password:
        handle = EmailNotificationHandle(from_email, to_email, password, smtp)
        notification_manager.addHandle(handle)
        enabled_channels.append("Email")

    # Telegram
    bot_token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")

    if bot_token and chat_id:
        handle = TelegramNotificationHandle(bot_token, chat_id)
        notification_manager.addHandle(handle)
        enabled_channels.append("Telegram")

    # Bark
    bark_device_key = os.getenv("BARK_DEVICE_KEY")
    bark_server_url = os.getenv("BARK_SERVER_URL") or "https://api.day.app"

    if bark_device_key:
        handle = BarkNotificationHandle(bark_device_key, bark_server_url)
        notification_manager.addHandle(handle)
        enabled_channels.append("Bark")

    return enabled_channels


def main():
    parser = argparse.ArgumentParser(description="CEAC Status Bot")
    parser.add_argument("--test", action="store_true", help="Send a test notification to verify channels are working")
    parser.add_argument("--manual-captcha", action="store_true", help="Manually input captcha instead of auto recognition")
    args = parser.parse_args()

    # Ensure status_record.json exists
    if not os.path.exists("status_record.json"):
        download_artifact()

    # Read required env vars
    try:
        location = os.environ["LOCATION"]
        number = os.environ["NUMBER"]
        passport_number = os.environ["PASSPORT_NUMBER"]
        surname = os.environ["SURNAME"]
    except KeyError as e:
        raise RuntimeError(f"Missing required env var: {e}") from e

    # Create notification manager with appropriate captcha handler
    if args.manual_captcha:
        captcha_handler = ManualCaptchaHandle()
        print("Using manual captcha input mode")
    else:
        captcha_handler = None  # Use default (OnnxCaptchaHandle)

    if captcha_handler:
        notification_manager = NotificationManager(location, number, passport_number, surname, captcha_handler)
    else:
        notification_manager = NotificationManager(location, number, passport_number, surname)
    enabled_channels = setup_notification_channels(notification_manager)

    # Show enabled channels
    if enabled_channels:
        print(f"Enabled notification channels: {', '.join(enabled_channels)}")
    else:
        print("Warning: No notification channels configured. Status changes will not be notified.")

    if args.test:
        # Send test notification
        print("Sending test notification...")
        notification_manager.test()
    else:
        # Normal operation
        notification_manager.send()


if __name__ == "__main__":
    main()

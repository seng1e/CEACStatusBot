import os

from .handle import CaptchaHandle


class ManualCaptchaHandle(CaptchaHandle):
    def __init__(self) -> None:
        super().__init__()

    def solve(self, image) -> str:
        captcha_path = os.path.abspath("captcha.jpg")
        with open(captcha_path, "wb") as f:
            f.write(image)
        print(f"\nCaptcha image saved to: {captcha_path}")
        res = input("Enter captcha: ").strip()
        return res
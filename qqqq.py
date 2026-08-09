import base64

import undetected_chromedriver as uc

from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


AUTH_URL = "https://21:weh234h234hw23g2@api-platejka.ru/api/lk/21"
PAGE_URL = "https://api-platejka.ru/api/lk/21"


class QRGeneratorError(Exception):
    pass


class SiteUnavailableError(QRGeneratorError):
    pass


class AuthenticationError(QRGeneratorError):
    pass


class QRGenerationError(QRGeneratorError):
    pass


def generate_qr(value: float) -> tuple[bytes, str]:
    driver = None

    try:
        # 1. Запускаем браузер
        try:
            driver = uc.Chrome(
                headless=True,
                use_subprocess=True,
            )

            driver.set_page_load_timeout(20)

        except Exception as e:
            raise SiteUnavailableError(
                "Не удалось запустить браузер"
            ) from e

        wait = WebDriverWait(driver, 20)

        # 2. Открываем сайт с авторизацией
        try:
            driver.get(AUTH_URL)

        except (TimeoutException, WebDriverException) as e:
            raise SiteUnavailableError(
                "Сайт недоступен"
            ) from e

        # 3. Открываем рабочую страницу
        try:
            driver.get(PAGE_URL)

        except (TimeoutException, WebDriverException) as e:
            raise SiteUnavailableError(
                "Не удалось открыть страницу агента"
            ) from e

        # 4. Проверяем авторизацию
        try:
            amount_input = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, '//*[@id="qr_amount"]')
                )
            )

        except TimeoutException as e:
            raise AuthenticationError(
                "Не удалось авторизоваться у агента"
            ) from e

        # 5. Вводим сумму
        amount_input.clear()
        amount_input.send_keys(str(value))

        # 6. Нажимаем создать
        try:
            create_btn = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//*[@id="qrSubmit"]')
                )
            )

            create_btn.click()

        except TimeoutException as e:
            raise QRGenerationError(
                "Не удалось нажать кнопку создания QR"
            ) from e

        # 7. Ждём появления готового QR
        try:
            wait.until(
                lambda d: (
                    d.find_element(By.XPATH,'//*[@id="qrImage"]')
                    .get_attribute("src") or ""
                ).startswith("data:image/")
            )

        except TimeoutException as e:
            raise QRGenerationError(
                "Агент не сгенерировал QR"
            ) from e

        # 8. Получаем картинку
        qr_image = driver.find_element(
            By.XPATH,'//*[@id="qrImage"]',
        )

        src = qr_image.get_attribute("src")

        if not src or "," not in src:
            raise QRGenerationError(
                "Агент не сгенерировал QR"
            )

        try:
            base64_data = src.split(",", 1)[1]
            image_data = base64.b64decode(base64_data)

        except Exception as e:
            raise QRGenerationError(
                "Не удалось получить изображение QR"
            ) from e

        # 9. Получаем данные для подписи
        try:
            data_field = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, '//*[ @ id = "qrUrlField"]')
                )
            )

            data = data_field.get_attribute("value")

        except TimeoutException as e:
            raise QRGenerationError(
                "QR создан, но данные не получены"
            ) from e

        if not data:
            raise QRGenerationError(
                "QR создан, но данные пустые"
            )

        return image_data, data

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
if __name__ == "__main__":
    try:
        qr, data = generate_qr(10000)

        print("QR успешно создан")
        print("DATA:", data)

        with open("debug_qr.png", "wb") as f:
            f.write(qr)

        print("Картинка сохранена в debug_qr.png")

    except Exception as e:
        print("ОШИБКА:", type(e).__name__)
        print(e)
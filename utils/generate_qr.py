import base64
import logging

import undetected_chromedriver as uc

from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import settings


logger = logging.getLogger(__name__)


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

    logger.info(
        "Начало генерации QR. amount=%s",
        value,
    )

    try:
        # --------------------------------------------------
        # 1. Запускаем браузер
        # --------------------------------------------------

        logger.info("Запуск Chrome")

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

        logger.info("Chrome успешно запущен")

        wait = WebDriverWait(driver, 20)

        # --------------------------------------------------
        # 2. Открываем сайт с авторизацией
        # --------------------------------------------------

        # AUTH_URL не выводим, потому что там логин/пароль
        logger.info(
            "Открытие страницы авторизации агента"
        )

        try:
            driver.get(settings.AUTH_URL)

        except TimeoutException as e:
            raise SiteUnavailableError(
                "Сайт недоступен"
            ) from e

        except WebDriverException as e:
            raise SiteUnavailableError(
                "Сайт недоступен"
            ) from e

        logger.info(
            "Страница авторизации открыта"
        )

        # --------------------------------------------------
        # 3. Открываем рабочую страницу
        # --------------------------------------------------

        logger.info(
            "Открытие рабочей страницы агента"
        )

        try:
            driver.get(settings.PAGE_URL)

        except TimeoutException as e:
            raise SiteUnavailableError(
                "Не удалось открыть страницу агента"
            ) from e

        except WebDriverException as e:
            raise SiteUnavailableError(
                "Не удалось открыть страницу агента"
            ) from e

        logger.info(
            "Рабочая страница агента открыта"
        )

        # --------------------------------------------------
        # 4. Проверяем авторизацию
        # --------------------------------------------------

        logger.info(
            "Проверка авторизации"
        )

        try:
            amount_input = wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        '//*[@id="qr_amount"]',
                    )
                )
            )

        except TimeoutException as e:
            raise AuthenticationError(
                "Не удалось авторизоваться у агента"
            ) from e

        logger.info(
            "Авторизация успешна"
        )

        # --------------------------------------------------
        # 5. Вводим сумму
        # --------------------------------------------------

        logger.info(
            "Ввод суммы: %s",
            value,
        )

        try:
            amount_input.clear()
            amount_input.send_keys(str(value))

        except WebDriverException as e:
            raise QRGenerationError(
                "Не удалось ввести сумму"
            ) from e

        logger.info(
            "Сумма успешно введена"
        )

        # --------------------------------------------------
        # 6. Нажимаем кнопку
        # --------------------------------------------------

        logger.info(
            "Поиск кнопки создания QR"
        )

        try:
            create_btn = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        '//*[@id="qrSubmit"]',
                    )
                )
            )

            create_btn.click()

        except TimeoutException as e:
            raise QRGenerationError(
                "Не удалось нажать кнопку создания QR"
            ) from e

        except WebDriverException as e:
            raise QRGenerationError(
                "Не удалось нажать кнопку создания QR"
            ) from e

        logger.info(
            "Кнопка создания QR нажата"
        )

        # --------------------------------------------------
        # 7. Ждём появления QR
        # --------------------------------------------------

        logger.info(
            "Ожидание генерации QR"
        )

        try:
            wait.until(
                lambda d: (
                    d.find_element(
                        By.XPATH,
                        '//*[@id="qrImage"]',
                    ).get_attribute("src") or ""
                ).startswith("data:image/")
            )

        except TimeoutException as e:
            raise QRGenerationError(
                "Агент не сгенерировал QR"
            ) from e

        logger.info(
            "QR успешно сгенерирован"
        )

        # --------------------------------------------------
        # 8. Получаем картинку
        # --------------------------------------------------

        logger.info(
            "Получение изображения QR"
        )

        try:
            qr_image = driver.find_element(
                By.XPATH,
                '//*[@id="qrImage"]',
            )

            src = qr_image.get_attribute("src")

        except WebDriverException as e:
            raise QRGenerationError(
                "Не удалось получить изображение QR"
            ) from e

        if not src or "," not in src:
            raise QRGenerationError(
                "Агент не сгенерировал QR"
            )

        try:
            base64_data = src.split(",", 1)[1]

            image_data = base64.b64decode(
                base64_data
            )

        except Exception as e:
            raise QRGenerationError(
                "Не удалось получить изображение QR"
            ) from e

        logger.info(
            "Изображение QR получено. size=%s bytes",
            len(image_data),
        )

        # --------------------------------------------------
        # 9. Получаем data
        # --------------------------------------------------

        logger.info(
            "Получение данных QR"
        )

        try:
            data_field = wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        '//*[@id="qrUrlField"]',
                    )
                )
            )

            data = data_field.get_attribute(
                "value"
            )

        except TimeoutException as e:
            raise QRGenerationError(
                "QR создан, но данные не получены"
            ) from e

        except WebDriverException as e:
            raise QRGenerationError(
                "QR создан, но данные не получены"
            ) from e

        if not data:
            raise QRGenerationError(
                "QR создан, но данные пустые"
            )

        logger.info(
            "QR полностью сформирован"
        )

        return image_data, data

    # ------------------------------------------------------
    # Наши ожидаемые ошибки
    # ------------------------------------------------------

    except QRGeneratorError:
        # logger.exception выводит:
        # - сообщение
        # - тип исключения
        # - полный traceback
        # - исходную ошибку из "raise ... from e"
        logger.exception(
            "Ошибка при генерации QR. amount=%s",
            value,
        )

        # Отдаём эту же ошибку обратно хендлеру бота
        raise

    # ------------------------------------------------------
    # Любая неожиданная ошибка
    # ------------------------------------------------------

    except Exception as e:
        logger.exception(
            "Непредвиденная ошибка при генерации QR. amount=%s",
            value,
        )

        raise QRGenerationError(
            "Произошла ошибка при генерации QR"
        ) from e

    finally:
        if driver:
            logger.info(
                "Закрытие Chrome"
            )

            try:
                driver.quit()

            except Exception:
                logger.exception(
                    "Ошибка при закрытии Chrome"
                )

        logger.info(
            "Завершение generate_qr. amount=%s",
            value,
        )
import base64
import logging
import time

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


# ============================================================
# Исключения
# ============================================================


class QRGeneratorError(Exception):
    """Базовая ошибка генерации QR."""


class SiteUnavailableError(QRGeneratorError):
    """Сайт агента недоступен."""


class AuthenticationError(QRGeneratorError):
    """Не удалось авторизоваться."""


class QRGenerationError(QRGeneratorError):
    """Ошибка генерации QR."""



def generate_qr(value: float, tab_index: int = 2) -> tuple[bytes, str]:
    if tab_index not in {2, 3, 4, 5}:
        raise QRGenerationError("Некорректный режим генерации QR")

    driver = None

    logger.info(
        "Начало генерации QR. amount=%s",
        value,
    )

    try:
        # 1. Запуск Chrome

        logger.info("Запуск Chrome")

        try:
            options = uc.ChromeOptions()

            # options.add_argument("--headless=new")
            # options.add_argument("--no-sandbox")
            # options.add_argument("--disable-dev-shm-usage")
            # options.add_argument("--disable-gpu")
            # options.add_argument("--disable-software-rasterizer")
            # options.add_argument("--window-size=1920,1080")

            driver = uc.Chrome(
                options=options,
                headless=False,
                use_subprocess=True,
            )

            driver.set_page_load_timeout(60)

        except Exception as e:
            logger.exception(
                "Не удалось запустить Chrome"
            )

            raise SiteUnavailableError(
                "Не удалось запустить браузер"
            ) from e

        logger.info("Chrome успешно запущен")

        # Ожидание элементов страницы.
        wait = WebDriverWait(driver, 20)

        # 2. Открываем URL с Basic Auth

        logger.info(
            "Открытие страницы авторизации агента"
        )

        start_time = time.perf_counter()

        try:
            driver.get(settings.AUTH_URL)

        except TimeoutException:
            elapsed = time.perf_counter() - start_time

            logger.warning(
                "Timeout при загрузке AUTH_URL "
                "через %.2f сек. "
                "Продолжаем работу.",
                elapsed,
            )

        except WebDriverException as e:
            logger.exception(
                "Ошибка при открытии AUTH_URL"
            )

            raise SiteUnavailableError(
                "Сайт агента недоступен"
            ) from e

        elapsed = time.perf_counter() - start_time

        logger.info(
            "AUTH_URL обработан за %.2f сек.",
            elapsed,
        )

        logger.info(
            "После AUTH_URL current_url=%s",
            driver.current_url,
        )

        logger.info(
            "Ожидание завершения авторизации"
        )

        time.sleep(2)

        # 3. Переходим на обычную страницу

        logger.info(
            "Открытие рабочей страницы агента"
        )

        start_time = time.perf_counter()

        try:
            driver.get(settings.PAGE_URL)

        except TimeoutException:
            elapsed = time.perf_counter() - start_time

            logger.warning(
                "Timeout при загрузке PAGE_URL "
                "через %.2f сек. "
                "Проверяем, успела ли загрузиться страница.",
                elapsed,
            )

        except WebDriverException as e:
            logger.exception(
                "Ошибка при открытии PAGE_URL"
            )

            raise SiteUnavailableError(
                "Не удалось открыть страницу агента"
            ) from e

        elapsed = time.perf_counter() - start_time

        logger.info(
            "PAGE_URL обработан за %.2f сек.",
            elapsed,
        )

        logger.info(
            "current_url=%s",
            driver.current_url,
        )

        logger.info(
            "title=%s",
            driver.title,
        )
        # 4. Выбор Р/С
        try:
            tab_button = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        f'//*[@id="kassaTabs"]/button[{tab_index}]',
                    )
                )
            )
            tab_button.click()

        except (TimeoutException, WebDriverException) as e:
            raise QRGenerationError(
                "Не удалось выбрать Р/С"
            ) from e

        logger.info(
            "Р/С выбран. tab_index=%s",
            tab_index,
        )

        # 5. Ввод суммы
        try:
            amount_input = wait.until(
                EC.presence_of_element_located(
                    (
                        By.ID,
                        "qr_amount",
                    )
                )
            )

            # Устанавливаем значение напрямую через JS.
            driver.execute_script(
                """
                const input = arguments[0];
                const value = arguments[1];

                const setter = Object.getOwnPropertyDescriptor(
                    HTMLInputElement.prototype,
                    'value'
                ).set;

                setter.call(input, value);

                input.dispatchEvent(
                    new Event('input', {
                        bubbles: true
                    })
                );

                input.dispatchEvent(
                    new Event('change', {
                        bubbles: true
                    })
                );

                input.dispatchEvent(
                    new Event('blur', {
                        bubbles: true
                    })
                );
                """,
                amount_input,
                str(value),
            )

        except WebDriverException as e:
            raise QRGenerationError(
                "Не удалось ввести сумму"
            ) from e

        logger.info(
            "Сумма успешно введена"
        )

        # 6. Нажимаем кнопку создания QR

        try:
            create_btn = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        '//*[@id="qrSubmit"]'
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

        # 7. Ожидаем готовый QR

        logger.info(
            "Ожидание генерации QR"
        )

        try:
            wait.until(
                lambda d: (
                    d.find_element(
                        By.XPATH,
                        '//*[@id="qrImage"]'
                    )
                    .get_attribute("src") or ""
                ).startswith("data:image/")
            )

        except TimeoutException as e:
            raise QRGenerationError(
                "Агент не сгенерировал QR"
            ) from e

        except WebDriverException as e:
            raise QRGenerationError(
                "Агент не сгенерировал QR"
            ) from e

        logger.info(
            "QR успешно сгенерирован"
        )

        # 8. Получаем изображение QR

        try:
            qr_image = driver.find_element(
                By.XPATH,
                '//*[@id="qrImage"]'
            )

            src = qr_image.get_attribute("src")

        except WebDriverException as e:
            raise QRGenerationError(
                "Не удалось получить изображение QR"
            ) from e

        if not src:
            raise QRGenerationError(
                "Агент не сгенерировал QR"
            )

        if not src.startswith("data:image/"):
            raise QRGenerationError(
                "Агент вернул некорректное изображение QR"
            )

        if "," not in src:
            raise QRGenerationError(
                "Агент вернул некорректное изображение QR"
            )

        # 9. Base64 -> bytes

        try:
            _, base64_data = src.split(",", 1)

            image_data = base64.b64decode(
                base64_data,
            )

        except Exception as e:
            raise QRGenerationError(
                "Не удалось получить изображение QR"
            ) from e

        if not image_data:
            raise QRGenerationError(
                "Изображение QR пустое"
            )

        logger.info(
            "Изображение QR получено."
        )

        # 10. Получаем данные для подписи

        try:
            data_field = wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        '//*[ @ id = "qrUrlField"]'
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

    # ошибки

    except QRGeneratorError:
        # В консоль попадёт:
        # - полный traceback
        # - исходная Selenium ошибка
        # - наша итоговая ошибка
        logger.exception(
            "Ошибка при генерации QR. amount=%s",
            value,
        )

        # Отдаём ошибку дальше Telegram handler'у.
        raise

    # Любая неизвестная ошибка

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

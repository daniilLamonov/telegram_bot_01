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


# ============================================================
# Генерация QR
# ============================================================


def generate_qr(value: float) -> tuple[bytes, str]:
    driver = None

    logger.info(
        "Начало генерации QR. amount=%s",
        value,
    )

    try:
        # --------------------------------------------------
        # 1. Запуск Chrome
        # --------------------------------------------------

        logger.info("Запуск Chrome")

        try:
            options = uc.ChromeOptions()

            # Не ждём загрузки абсолютно всех ресурсов страницы.
            options.page_load_strategy = "eager"

            # Настройки для Docker / сервера.
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")

            driver = uc.Chrome(
                options=options,
                browser_executable_path="/usr/bin/google-chrome",
                use_subprocess=True,
            )

            # Максимальное время driver.get()
            driver.set_page_load_timeout(60)

        except Exception as e:
            raise SiteUnavailableError(
                "Не удалось запустить браузер"
            ) from e

        logger.info("Chrome успешно запущен")

        # Ожидание элементов страницы.
        wait = WebDriverWait(driver, 20)

        # --------------------------------------------------
        # 2. Открываем URL с Basic Auth
        # --------------------------------------------------

        # AUTH_URL в лог не выводим:
        # там находятся логин и пароль.
        logger.info(
            "Открытие страницы авторизации агента"
        )

        try:
            driver.get(settings.AUTH_URL)

        except TimeoutException:
            # Chrome иногда считает страницу ещё загружающейся,
            # хотя DOM уже доступен.
            logger.warning(
                "Timeout при загрузке AUTH_URL. "
                "Пробуем продолжить работу."
            )

        except WebDriverException as e:
            raise SiteUnavailableError(
                "Сайт агента недоступен"
            ) from e

        try:
            logger.info(
                "AUTH_URL обработан. current_url=%s",
                driver.current_url,
            )
        except Exception:
            logger.warning(
                "Не удалось получить current_url после AUTH_URL"
            )

        # --------------------------------------------------
        # 3. Открываем рабочую страницу
        # --------------------------------------------------

        logger.info(
            "Открытие рабочей страницы агента"
        )

        try:
            driver.get(settings.PAGE_URL)

        except TimeoutException:
            logger.warning(
                "Timeout при загрузке PAGE_URL. "
                "Пробуем продолжить работу."
            )

        except WebDriverException as e:
            raise SiteUnavailableError(
                "Не удалось открыть страницу агента"
            ) from e

        try:
            logger.info(
                "PAGE_URL обработан. current_url=%s",
                driver.current_url,
            )
        except Exception:
            logger.warning(
                "Не удалось получить current_url после PAGE_URL"
            )

        # --------------------------------------------------
        # 4. Проверяем авторизацию
        # --------------------------------------------------

        logger.info(
            "Проверка авторизации. Ожидание qr_amount"
        )

        try:
            amount_input = wait.until(
                EC.presence_of_element_located(
                    (
                        By.ID,
                        "qr_amount",
                    )
                )
            )

        except TimeoutException as e:
            try:
                logger.error(
                    "Поле qr_amount не найдено. "
                    "current_url=%s title=%s",
                    driver.current_url,
                    driver.title,
                )
            except Exception:
                logger.error(
                    "Поле qr_amount не найдено"
                )

            raise AuthenticationError(
                "Не удалось авторизоваться у агента"
            ) from e

        except WebDriverException as e:
            raise AuthenticationError(
                "Не удалось проверить авторизацию у агента"
            ) from e

        logger.info(
            "Авторизация успешна"
        )

        # --------------------------------------------------
        # 5. Ввод суммы
        # --------------------------------------------------

        logger.info(
            "Ввод суммы. amount=%s",
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
        # 6. Нажимаем кнопку создания QR
        # --------------------------------------------------

        logger.info(
            "Ожидание кнопки qrSubmit"
        )

        try:
            create_btn = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.ID,
                        "qrSubmit",
                    )
                )
            )

            logger.info(
                "Кнопка qrSubmit найдена"
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
        # 7. Ожидаем готовый QR
        # --------------------------------------------------

        logger.info(
            "Ожидание генерации QR"
        )

        try:
            wait.until(
                lambda d: (
                    d.find_element(
                        By.ID,
                        "qrImage",
                    ).get_attribute("src") or ""
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

        # --------------------------------------------------
        # 8. Получаем изображение QR
        # --------------------------------------------------

        logger.info(
            "Получение изображения QR"
        )

        try:
            qr_image = driver.find_element(
                By.ID,
                "qrImage",
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

        # --------------------------------------------------
        # 9. Base64 -> bytes
        # --------------------------------------------------

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
            "Изображение QR получено. size=%s bytes",
            len(image_data),
        )

        # --------------------------------------------------
        # 10. Получаем данные для подписи
        # --------------------------------------------------

        logger.info(
            "Получение qrUrlField"
        )

        try:
            data_field = wait.until(
                EC.presence_of_element_located(
                    (
                        By.ID,
                        "qrUrlField",
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

    # ========================================================
    # Наши контролируемые ошибки
    # ========================================================

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

    # ========================================================
    # Любая неизвестная ошибка
    # ========================================================

    except Exception as e:
        logger.exception(
            "Непредвиденная ошибка при генерации QR. amount=%s",
            value,
        )

        raise QRGenerationError(
            "Произошла ошибка при генерации QR"
        ) from e

    # ========================================================
    # Всегда закрываем Chrome
    # ========================================================

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
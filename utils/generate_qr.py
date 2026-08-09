import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from time import sleep



def generate_qr(value):

    driver = uc.Chrome(version_main=149, headless=True, use_subprocess=False)

    driver.get(
        "https://2:awfwaf21fwqf21g123g13g1@api-platejka.ru/api/lk/2"
    )
    sleep(2)
    driver.get('https://api-platejka.ru/api/lk/2')

    sleep(2)

    driver.find_element(
        By.XPATH,
        '//*[@id="qr_amount"]'
    ).send_keys(value)
    create_btn = driver.find_element(
        By.XPATH,
        '//*[@id="qrSubmit"]'
    )
    create_btn.click()
    sleep(2)


    #
    qr = driver.save_screenshot('3.png')
    data = driver.find_element_by_xpath('//*[@id="qr_amount"]').text
    #


    return qr, data
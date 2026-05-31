import time
import random
import json
import logging
import sys
from getpass import getpass

from bs4 import BeautifulSoup
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

import constants
try:
    import creds
except ModuleNotFoundError:
    print("\n\nYou must copy 'sample_creds.py' to 'creds.py' and update with your Vudu credentials\n\n")
    sys.exit(1)

#  Define log directory and output directory, and create them if they don't exist
log_dir = Path(__file__).resolve().parent.joinpath(constants.LOG_DIR)
output_dir = Path(__file__).resolve().parent.joinpath(constants.OUTPUT_DIR)

for directory in [log_dir, output_dir]:
    Path(directory).mkdir(exist_ok=True)

#region Set up logging
logging_level_file = getattr(logging, constants.LOGGING_LEVEL_FILE.upper(), logging.DEBUG)
logging_level_console = getattr(logging, constants.LOGGING_LEVEL_CONSOLE.upper(), logging.INFO)

# Create a custom logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Capture all logs, handlers will filter levels

# Create handlers
file_handler = logging.FileHandler(f'{log_dir}/{constants.LOG_FILE}')
file_handler.setLevel(logging_level_file)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging_level_console)

# Create formatters and add them to handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)
#endregion logging setup

driver = None


def create_chrome_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')  # Prevent detection as a bot
    options.add_argument('--disable-gpu')  # Disable GPU acceleration
    options.add_argument('--window-size=1920,1080')  # Set window size
    options.add_argument('--no-sandbox')  # Bypass OS security model
    options.add_argument('--disable-dev-shm-usage')  # Overcome limited resource problems
    options.add_argument('--disable-webgl')  # Disable WebGL
    options.add_argument('--disable-usb')  # Disable USB
    return webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()), options=options
    )


def login_to_vudu(email, password):
    try:
        driver.get(constants.VUDU_LOGIN_URL)
        logger.info("Navigated to Vudu login page")

        wait = WebDriverWait(driver, 10)

        # Enter email and password
        email_input = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, constants.EMAIL_ELEMENT))
        )
        email_input.clear()
        email_input.send_keys(email)

        password_input = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, constants.PASSWORD_ELEMENT))
        )
        password_input.clear()
        password_input.send_keys(password)
        password_input.send_keys(Keys.RETURN)
        time.sleep(random.uniform(5, 6))  # Random wait
        logger.info("Logged into Vudu successfully")
    except Exception:
        with open(f'{log_dir}/error_page_source_fn-login.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logger.exception("Error during login")
        raise


def simulate_keyboard_navigation(driver):
    actions = ActionChains(driver)
    wait = WebDriverWait(driver, 10)
    
    try:
        # Find the first movie element to start the keyboard navigation
        start_element = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, f'{constants.MOVIE_ELEMENT}.{constants.MOVIE_ELEMENT_CLASS}')
            )
        )
        logger.debug("Found start element for keyboard navigation")
    except Exception as e:
        # Capture page source for debugging
        with open(f'{log_dir}/error_page_source_fn-skn.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logger.exception("Error finding start element")
        raise e
    
    # Focus on the element without clicking
    driver.execute_script("arguments[0].focus();", start_element)
    time.sleep(2)  # Wait to ensure the element is focused
    
    loaded_items = set()
    previous_count = 0
    attempts = 0
    
    while attempts < 3:  # Try up to 4 times to scroll and load new content
        for _ in range(10):  
            # Number of down-arrow actions before reading new movie cards. Adjust as needed
            actions.send_keys(Keys.ARROW_DOWN).perform()
            time.sleep(random.uniform(0.1, 0.2))  # Random wait to mimic human behavior

        # Capture the visible items
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        for poster_div in soup.find_all(constants.MOVIE_ELEMENT, class_=constants.MOVIE_ELEMENT_CLASS):
            img_tag = poster_div.find('img', alt=True)
            if img_tag:
                title = img_tag['alt']
                position = (poster_div['style'], title)  # Using position in style as index
                loaded_items.add(position)

        current_count = len(loaded_items)
        logger.info(f'Loaded items: {current_count}')  # Debug statement
        
        if current_count > previous_count:
            attempts = 0  # Reset attempts if new content is loaded
        else:
            attempts += 1
        
        logger.debug(f'Attempts: {attempts}')  # Debug statement
        previous_count = current_count

        # Adding a more extended wait if no new content is loaded
        if attempts == 2:
            logger.info("Waiting longer to ensure all content loads...")
            time.sleep(2)
    
    return loaded_items


def get_purchased_content(url):
    driver.get(url)
    wait = WebDriverWait(driver, 10)
    try:
        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, f'{constants.MOVIE_ELEMENT}.{constants.MOVIE_ELEMENT_CLASS}')
            )
        )
    except Exception:
        # Capture page source for debugging
        with open(f'{log_dir}/error_page_source_fn-gpc-{url.split("/")[-1]}.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        logger.exception(f"Error navigating to {url}")
        raise
    loaded_items = simulate_keyboard_navigation(driver)
    content = list({title for _, title in loaded_items})
    logger.info(f'Retrieved {len(content)} items from {url}')
    return content


def custom_sort(title):
    articles = ["A ", "An ", "The "]
    for article in articles:
        if title.startswith(article) and len(title) > len(article):
            return title[len(article):]
    return title


def get_vudu_password():
    input_method = getattr(creds, "VUDU_PASSWD_INPUT_METHOD", 1)

    if input_method == 0:
        return getpass("Vudu password: ")

    if input_method == 1:
        return creds.VUDU_PASSWD

    raise ValueError("VUDU_PASSWD_INPUT_METHOD must be 0 for prompted or 1 for hardcoded")


def main():
    global driver

    try:
        password = get_vudu_password()
        driver = create_chrome_driver()
        login_to_vudu(creds.VUDU_LOGIN, password)
        
        #  Retrieve movie list
        movies = get_purchased_content(constants.VUDU_MYMOVIES_URL)
        movies.sort(key=custom_sort)
        logger.debug(f'Movies: {movies}')
        
        #  Retrieve TV show list
        tv_shows = get_purchased_content(constants.VUDU_MYTV_URL)
        tv_shows.sort(key=custom_sort)
        logger.debug(f'TV Shows: {tv_shows}')
        
        #  Write the lists to JSON files
        with open(f'{output_dir}/{constants.MOVIE_LIST_FILE}', 'w') as f:
            f.write(json.dumps(movies, indent=4))
        with open(f'{output_dir}/{constants.TV_LIST_FILE}', 'w') as f:
            f.write(json.dumps(tv_shows, indent=4))
    except Exception:
        logger.critical("Critical error in main execution", exc_info=True)
    finally:
        if driver is not None:
            driver.quit()
        logger.info("Closed the browser and ended the session")


if __name__ == '__main__':
    main()
    

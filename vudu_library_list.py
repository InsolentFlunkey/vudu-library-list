import time
import random
import json
import logging
import re
import sys
from getpass import getpass

from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin
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
metadata_debug_dir = log_dir.joinpath("metadata_debug")

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
YEAR_PATTERN = re.compile(r'\b(?:19|20)\d{2}\b')
FORMAT_PATTERN = re.compile(r'\b(?:4K UHD|UHD|HDX|HD|SD)\b', re.IGNORECASE)
SEASON_PATTERN = re.compile(r'\bSeason\s+(\d{1,2})\b', re.IGNORECASE)
metadata_debug_count = 0
MAX_METADATA_DEBUG_FILES = 10


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


def clean_text(value):
    return re.sub(r'\s+', ' ', value).strip()


def iter_relevant_attribute_values(element):
    for attr_name, attr_value in element.attrs.items():
        if attr_name in {"alt", "aria-label", "title"} or attr_name.startswith("data-"):
            if isinstance(attr_value, list):
                yield " ".join(attr_value)
            else:
                yield str(attr_value)


def extract_owned_format(text):
    match = FORMAT_PATTERN.search(text)
    if match:
        return match.group(0).upper()
    return None


def extract_metadata_from_text(text):
    clean_value = clean_text(text)
    year_match = YEAR_PATTERN.search(clean_value)

    return {
        "year": int(year_match.group(0)) if year_match else None,
        "owned_format": extract_owned_format(clean_value),
    }


def extract_content_item(poster_div):
    img_tag = poster_div.find('img', alt=True)
    if not img_tag:
        return None

    link_tag = poster_div.find('a', href=True)
    title = clean_text(img_tag['alt'])
    card_text_parts = list(poster_div.stripped_strings)

    for element in poster_div.descendants:
        if getattr(element, "attrs", None):
            card_text_parts.extend(iter_relevant_attribute_values(element))

    metadata = extract_metadata_from_text(" ".join(card_text_parts))

    return {
        "title": title,
        "year": metadata["year"],
        "owned_format": metadata["owned_format"],
        "content_url": urljoin(constants.VUDU_MAIN_URL, link_tag['href']) if link_tag else None,
        "poster_url": urljoin(constants.VUDU_MAIN_URL, img_tag['src']) if img_tag.get('src') else None,
    }


def merge_item_metadata(existing_item, new_item):
    if existing_item is None:
        return new_item

    return {
        "title": existing_item["title"],
        "year": existing_item["year"] or new_item["year"],
        "owned_format": existing_item["owned_format"] or new_item["owned_format"],
        "content_url": existing_item["content_url"] or new_item["content_url"],
        "poster_url": existing_item["poster_url"] or new_item["poster_url"],
    }


def get_item_key(item):
    if item["content_url"]:
        return item["content_url"]
    if item["year"]:
        return item["title"], item["year"]
    return item["title"], item["owned_format"]


def get_viewport_poster_elements(driver):
    selector = f'{constants.MOVIE_ELEMENT}.{constants.MOVIE_ELEMENT_CLASS}'
    return driver.execute_script(
        """
        return Array.from(document.querySelectorAll(arguments[0])).filter((element) => {
            const rect = element.getBoundingClientRect();
            return (
                rect.width > 0 &&
                rect.height > 0 &&
                rect.bottom > 0 &&
                rect.top < window.innerHeight &&
                rect.right > 0 &&
                rect.left < window.innerWidth
            );
        });
        """,
        selector,
    )


def extract_basic_content_item(poster_element):
    poster_html = poster_element.get_attribute("outerHTML")
    soup = BeautifulSoup(poster_html, 'html.parser')
    poster_div = soup.find(constants.MOVIE_ELEMENT, class_=constants.MOVIE_ELEMENT_CLASS)
    return extract_content_item(poster_div) if poster_div else None


def get_hover_metadata_text(driver, poster_element):
    return driver.execute_script(
        """
        const element = arguments[0];
        const title = arguments[1];
        const metadataPattern = /You have|4K UHD|HDX|\\bHD\\b|\\bSD\\b|\\b(?:19|20)\\d{2}\\b/i;
        let current = element;
        let fallbackText = '';

        for (let depth = 0; current && depth < 7; depth += 1) {
            const text = current.innerText || current.textContent || '';
            if (text.trim()) {
                fallbackText = text;
            }
            if (metadataPattern.test(text)) {
                return text;
            }
            current = current.parentElement;
        }

        const elementRect = element.getBoundingClientRect();
        const elementCenterX = elementRect.left + elementRect.width / 2;
        const elementCenterY = elementRect.top + elementRect.height / 2;
        const candidates = Array.from(document.body.querySelectorAll('*'))
            .filter((candidate) => {
                const text = candidate.innerText || candidate.textContent || '';
                if (!metadataPattern.test(text) && !text.includes(title)) {
                    return false;
                }

                const rect = candidate.getBoundingClientRect();
                return (
                    rect.width > 0 &&
                    rect.height > 0 &&
                    rect.bottom > 0 &&
                    rect.top < window.innerHeight &&
                    rect.right > 0 &&
                    rect.left < window.innerWidth
                );
            })
            .map((candidate) => {
                const rect = candidate.getBoundingClientRect();
                const centerX = rect.left + rect.width / 2;
                const centerY = rect.top + rect.height / 2;
                const distance = Math.hypot(centerX - elementCenterX, centerY - elementCenterY);
                return {
                    text: candidate.innerText || candidate.textContent || '',
                    distance,
                };
            })
            .sort((left, right) => left.distance - right.distance);

        const candidate = candidates.find((item) => metadataPattern.test(item.text));
        if (candidate) {
            return candidate.text;
        }

        return fallbackText;
        """,
        poster_element,
        item_title_from_element(poster_element),
    )


def item_title_from_element(poster_element):
    img_tag = poster_element.find_element(By.CSS_SELECTOR, "img[alt]")
    return img_tag.get_attribute("alt")


def trigger_hover(driver, poster_element, actions):
    actions.move_to_element(poster_element).perform()
    driver.execute_script(
        """
        const element = arguments[0];
        const targets = [
            element,
            element.querySelector('a'),
            element.querySelector('img'),
        ].filter(Boolean);

        for (const target of targets) {
            const rect = target.getBoundingClientRect();
            const eventOptions = {
                bubbles: true,
                cancelable: true,
                clientX: rect.left + rect.width / 2,
                clientY: rect.top + rect.height / 2,
                view: window,
            };
            target.dispatchEvent(new MouseEvent('mouseover', eventOptions));
            target.dispatchEvent(new MouseEvent('mouseenter', eventOptions));
            target.dispatchEvent(new MouseEvent('mousemove', eventOptions));
        }
        """,
        poster_element,
    )


def safe_filename(value):
    return re.sub(r'[^A-Za-z0-9._-]+', '-', value).strip('-')[:80] or "item"


def write_metadata_debug_file(driver, poster_element, item, hover_text):
    global metadata_debug_count

    if metadata_debug_count >= MAX_METADATA_DEBUG_FILES:
        return

    metadata_debug_dir.mkdir(exist_ok=True)
    metadata_debug_count += 1

    debug_path = metadata_debug_dir.joinpath(
        f'{metadata_debug_count:02d}-{safe_filename(item["title"])}.html'
    )
    debug_html = driver.execute_script(
        """
        const element = arguments[0];
        const hoverText = arguments[1];
        const item = arguments[2];
        const ancestors = [];
        let current = element;

        for (let depth = 0; current && depth < 7; depth += 1) {
            ancestors.push({
                depth,
                tag: current.tagName,
                className: current.className,
                text: current.innerText || current.textContent || '',
                html: current.outerHTML,
            });
            current = current.parentElement;
        }

        return `<pre>${JSON.stringify({ item, hoverText, ancestors }, null, 2)}</pre>`;
        """,
        poster_element,
        hover_text,
        item,
    )

    with open(debug_path, 'w', encoding='utf-8') as f:
        f.write(debug_html)

    logger.info(f'Wrote metadata debug file: {debug_path}')


def extract_hovered_content_item(driver, poster_element, actions, base_item):
    trigger_hover(driver, poster_element, actions)
    time.sleep(random.uniform(0.15, 0.25))
    hover_text = ""

    for _ in range(5):
        hover_text = get_hover_metadata_text(driver, poster_element)
        metadata = extract_metadata_from_text(hover_text)
        if metadata["year"] or metadata["owned_format"]:
            return merge_item_metadata(base_item, {
                **base_item,
                **metadata,
            })
        time.sleep(0.15)

    write_metadata_debug_file(driver, poster_element, base_item, hover_text)
    return base_item


def extract_visible_content_items(driver, actions, loaded_items):
    items = []
    poster_elements = get_viewport_poster_elements(driver)

    for poster_element in poster_elements:
        try:
            item = extract_basic_content_item(poster_element)
            if not item:
                continue

            item_key = get_item_key(item)
            if item_key in loaded_items:
                continue

            item = extract_hovered_content_item(driver, poster_element, actions, item)
        except Exception:
            logger.debug("Unable to extract content poster metadata", exc_info=True)
            continue

        if item:
            items.append(item)

    return items


def focus_first_viewport_poster(driver):
    poster_elements = get_viewport_poster_elements(driver)
    if poster_elements:
        driver.execute_script("arguments[0].focus();", poster_elements[0])


def scroll_content_list(driver):
    driver.execute_script(
        """
        const selector = arguments[0];
        const poster = document.querySelector(selector);
        const scrollTarget =
            poster?.closest('[style*="overflow"]') ||
            document.scrollingElement ||
            document.documentElement;
        const distance = Math.floor(window.innerHeight * 0.75);
        scrollTarget.scrollBy({ top: distance, behavior: 'instant' });
        """,
        f'{constants.MOVIE_ELEMENT}.{constants.MOVIE_ELEMENT_CLASS}',
    )


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
    
    loaded_items = {}
    previous_count = 0
    attempts = 0
    
    while attempts < 3:  # Try up to 4 times to scroll and load new content
        focus_first_viewport_poster(driver)

        # Capture the visible items, hovering first so overlay metadata can render.
        for item in extract_visible_content_items(driver, actions, loaded_items):
            item_key = get_item_key(item)
            loaded_items[item_key] = merge_item_metadata(
                loaded_items.get(item_key),
                item,
            )

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

        if attempts < 3:
            scroll_content_list(driver)
            time.sleep(random.uniform(0.6, 0.8))  # Random wait to mimic human behavior
    
    return list(loaded_items.values())


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
    content = loaded_items
    logger.info(f'Retrieved {len(content)} items from {url}')
    return content


def get_detail_page_counts():
    return driver.execute_script(
        """
        const detailLinks = Array.from(document.querySelectorAll('a[href*="/content/browse/details/"]'))
            .filter((link) => link.querySelector('img[alt]'))
            .length;
        const bodyText = document.body?.innerText || '';
        const seasonMatches = bodyText.match(/\\bSeason\\s+\\d{1,2}\\b/gi) || [];

        return {
            detailLinks,
            seasonMatches: seasonMatches.length,
            textLength: bodyText.length,
        };
        """
    )


def wait_for_detail_page():
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))

    stable_count = 0
    previous_counts = None
    deadline = time.time() + 8

    while time.time() < deadline:
        counts = get_detail_page_counts()
        if counts == previous_counts and counts["textLength"] > 0:
            stable_count += 1
            if stable_count >= 3:
                return
        else:
            stable_count = 0
            previous_counts = counts

        time.sleep(0.5)


def get_detail_page_soup(url):
    driver.get(url)
    wait_for_detail_page()
    return BeautifulSoup(driver.page_source, 'html.parser')


def normalize_content_url(url):
    return url.split("?")[0].rstrip("/") if url else None


def clean_detail_title(value):
    return re.sub(r'\s+poster$', '', clean_text(value), flags=re.IGNORECASE)


def extract_detail_page_content_items(soup, current_item):
    current_url = normalize_content_url(current_item.get("content_url"))
    items = {}

    for link_tag in soup.find_all("a", href=True):
        href = link_tag["href"]
        if "/content/browse/details/" not in href:
            continue

        img_tag = link_tag.find("img", alt=True)
        if not img_tag:
            continue

        content_url = normalize_content_url(urljoin(constants.VUDU_MAIN_URL, href))
        if content_url == current_url:
            continue

        title = clean_detail_title(img_tag["alt"])
        if not title or title == current_item["title"]:
            continue

        items[content_url] = {
            "title": title,
            "content_url": content_url,
            "poster_url": urljoin(constants.VUDU_MAIN_URL, img_tag["src"]) if img_tag.get("src") else None,
        }

    return list(items.values())


def enrich_movie_bundles(movies):
    bundle_movies = [
        movie for movie in movies
        if "bundle" in movie["title"].lower() and movie.get("content_url")
    ]

    logger.info(f'Enriching {len(bundle_movies)} movie bundles')

    for movie in bundle_movies:
        try:
            soup = get_detail_page_soup(movie["content_url"])
            movie["bundle_titles"] = extract_detail_page_content_items(soup, movie)
            movie["bundle_title_count"] = len(movie["bundle_titles"])
            logger.info(f'Retrieved {movie["bundle_title_count"]} bundle titles for {movie["title"]}')
        except Exception:
            movie["bundle_titles"] = []
            movie["bundle_title_count"] = 0
            logger.exception(f'Error retrieving bundle titles for {movie["title"]}')


def extract_tv_seasons(soup):
    page_text = soup.get_text(" ", strip=True)
    season_numbers = sorted({int(match) for match in SEASON_PATTERN.findall(page_text)})
    return season_numbers


def enrich_tv_seasons(tv_shows):
    logger.info(f'Enriching season counts for {len(tv_shows)} TV titles')

    for tv_show in tv_shows:
        tv_show["owned_seasons"] = []
        tv_show["season_count"] = None

        if not tv_show.get("content_url"):
            continue

        try:
            soup = get_detail_page_soup(tv_show["content_url"])
            owned_seasons = extract_tv_seasons(soup)
            tv_show["owned_seasons"] = owned_seasons
            tv_show["season_count"] = len(owned_seasons) if owned_seasons else None
            logger.info(f'Retrieved {tv_show["season_count"] or 0} seasons for {tv_show["title"]}')
        except Exception:
            logger.exception(f'Error retrieving seasons for {tv_show["title"]}')


def custom_sort(item):
    title = item["title"]
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
        enrich_movie_bundles(movies)
        logger.debug(f'Movies: {movies}')
        
        #  Retrieve TV show list
        tv_shows = get_purchased_content(constants.VUDU_MYTV_URL)
        tv_shows.sort(key=custom_sort)
        enrich_tv_seasons(tv_shows)
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
    

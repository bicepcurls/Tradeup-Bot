import time
import random
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import csv
from tqdm import tqdm

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.142 Safari/537.36"
]

# Selenium WebDriver setup
def setup_selenium_driver():
    options = Options()
    options.add_argument('--headless')  # Run in headless mode (no browser UI)
    options.add_argument('--disable-gpu')  # Disable GPU for headless mode
    driver = webdriver.Chrome(options=options)  # Adjust path to ChromeDriver if necessary
    return driver

def fetch_page_with_selenium(url, driver, retries=3):
    attempt = 0
    while attempt < retries:
        try:
            driver.get(url)
            # Wait for the page to fully load (adjust the timeout if necessary)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.market_listing_row_link'))
            )
            time.sleep(random.uniform(3, 6))  # Extra wait to ensure the content loads completely
            return driver.page_source
        except Exception as e:
            logger.error(f"Error fetching {url} with Selenium: {e}. Retrying...")
            attempt += 1
            time.sleep(random.uniform(6, 10))  # Increased wait time
    logger.error(f"Failed to fetch {url} after {retries} retries.")
    return None

def scrape_skins(page_source, scraped_skins):
    skins = []
    soup = BeautifulSoup(page_source, 'html.parser')
    items = soup.find_all('a', {'class': 'market_listing_row_link'})
    logger.info(f"Found {len(items)} items on this page.")

    for item in items:
        try:
            skin_name = item.find('span', {'class': 'market_listing_item_name'}).text.strip()
            price_span = item.find('span', {'class': 'sale_price'})
            price = price_span.text.strip() if price_span else 'N/A'

            # Generate a unique identifier using multiple factors, not just name and price
            skin_link = item['href']  # Add the link as a unique identifier
            unique_identifier = f"{skin_name}_{price}_{skin_link}"

            # Ensure uniqueness by checking multiple identifiers
            if unique_identifier not in scraped_skins:
                scraped_skins.add(unique_identifier)  # Add to the set to track uniqueness
                skins.append({'skin_name': skin_name, 'price': price, 'link': skin_link})
                logger.info(f"Scraped skin: {skin_name} - {price}")
            else:
                logger.info(f"Skipping duplicate: {skin_name} - {price}")
        except AttributeError as e:
            logger.error(f"Error extracting item: {e}")
            continue

    return skins

def save_skins_to_csv(skins, filename='all_skins.csv'):
    """ Save scraped skins to CSV incrementally. """
    fieldnames = ['skin_name', 'price', 'link']
    file_exists = False
    
    try:
        # Check if file exists to avoid overwriting
        with open(filename, 'r', encoding='utf-8') as f:
            file_exists = True
    except FileNotFoundError:
        pass  # File doesn't exist, will create it
    
    with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()  # Write header if it's the first write
        writer.writerows(skins)
        logger.info(f"Saved {len(skins)} skins to {filename}.")

def scrape_all_skins(base_url="https://steamcommunity.com/market/search?q=&category_730_ItemSet%5B0%5D=any&category_730_ProPlayer%5B0%5D=any&category_730_StickerCapsule%5B0%5D=any&category_730_Tournament%5B0%5D=any&category_730_TournamentTeam%5B0%5D=any&category_730_Type%5B0%5D=any&category_730_Weapon%5B0%5D=any&category_730_Rarity%5B0%5D=tag_Rarity_Common_Weapon&appid=730", total_skins_needed=1141):
    start = 0
    all_skins = []
    total_scraped = 0
    max_pages = 115  # Steam has 115 pages in total
    max_retries = 3  # Maximum retries for each page

    driver = setup_selenium_driver()  # Set up the Selenium WebDriver
    scraped_skins = set()  # Set to keep track of unique skins across all pages

    # Scrape until we reach the target number of unique skins
    while total_scraped < total_skins_needed:
        for page_num in tqdm(range(start, start + max_pages), desc="Scraping skins", ncols=100):
            url = f"{base_url}&start={page_num * 10}"
            logger.info(f"Scraping page {page_num + 1} (start={page_num * 10})...")

            # Fetch the page using Selenium
            page_source = fetch_page_with_selenium(url, driver, retries=max_retries)
            if not page_source:
                logger.warning(f"Failed to load page starting at {page_num * 10}. Skipping...")
                continue

            # Scrape skins from the page
            page_skins = scrape_skins(page_source, scraped_skins)
            unique_skins = []

            # Only add unique skins
            for skin in page_skins:
                skin_id = f"{skin['skin_name']}_{skin['price']}"
                if skin_id not in scraped_skins:
                    scraped_skins.add(skin_id)
                    unique_skins.append(skin)
                    total_scraped += 1  # Increment the counter for each unique skin

                if total_scraped >= total_skins_needed:
                    logger.info(f"Reached target of {total_skins_needed} unique skins. Stopping.")
                    break

            # Add the unique skins to the total collection
            all_skins.extend(unique_skins)

            # Save the unique skins to CSV after each page scrape
            save_skins_to_csv(unique_skins)

        # If we haven't reached the target, retry failed pages
        if total_scraped < total_skins_needed:
            logger.warning(f"Still need {total_skins_needed - total_scraped} unique skins. Retrying the pages...")
            # Retry pages that failed earlier
            start = 0  # Restart the scraping process to retry
        else:
            break

    driver.quit()  # Close the Selenium WebDriver after scraping is done
    return all_skins

if __name__ == "__main__":
    all_skins = scrape_all_skins()
    logger.info(f"Found {len(all_skins)} unique skins in total.")
    logger.info("Scraping complete.")


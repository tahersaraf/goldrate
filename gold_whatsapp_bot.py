"""
Gold Rate WhatsApp Bot
======================
Scrapes today's gold prices (22K & 24K) for Indian cities
and sends a formatted message via WhatsApp Web using Selenium.

Usage:
    python gold_whatsapp_bot.py

Requirements:
    pip install selenium webdriver-manager

Config:
    Edit config.py to set your WhatsApp contact names/numbers
    and the cities you want gold rates for.
"""

import os
import sys
import time
import logging
import tempfile
from pathlib import Path
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    SessionNotCreatedException,
    TimeoutException,
    NoSuchElementException,
)
from webdriver_manager.chrome import ChromeDriverManager

from config import CONTACTS, CITIES, WHATSAPP_PROFILE_DIR, HEADLESS

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gold Scraper
# ---------------------------------------------------------------------------
class GoldScraper:
    """Scrapes today's gold rates from goodreturns.in."""

    BASE_URL = "https://www.goodreturns.in/gold-rates/"

    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver

    def fetch_rates(self, cities: list[str]) -> dict[str, dict]:
        """
        Returns a dict like:
          { "Mumbai": {"22K": "₹5,900", "24K": "₹6,400"}, ... }
        """
        rates: dict[str, dict] = {}
        for city in cities:
            try:
                city_rates = self._fetch_city(city)
                rates[city] = city_rates
                log.info("Fetched rates for %s: %s", city, city_rates)
            except Exception as exc:
                log.warning("Could not fetch rates for %s: %s", city, exc)
                rates[city] = {"22K": "N/A", "24K": "N/A"}
        return rates

    def _fetch_city(self, city: str) -> dict:
        city_slug = city.lower().replace(" ", "-")
        url = f"{self.BASE_URL}{city_slug}.html"
        self.driver.get(url)

        wait = WebDriverWait(self.driver, 15)

        # Wait for the rate table to appear
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))

        rate_22k = self._extract_rate("22K")
        rate_24k = self._extract_rate("24K")
        return {"22K": rate_22k, "24K": rate_24k}

    def _extract_rate(self, karat: str) -> str:
        """Finds a table row containing the karat label and reads the price."""
        try:
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table tr")
            for row in rows:
                text = row.text
                if karat in text:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    for cell in cells:
                        cell_text = cell.text.strip()
                        # Pick the cell that looks like a rupee amount
                        if cell_text and ("₹" in cell_text or cell_text.replace(",", "").isdigit()):
                            price = cell_text
                            if not price.startswith("₹"):
                                price = f"₹{price}"
                            return price
        except NoSuchElementException:
            pass
        return "N/A"


# ---------------------------------------------------------------------------
# Message Formatter
# ---------------------------------------------------------------------------
def build_message(rates: dict[str, dict]) -> str:
    today = datetime.now().strftime("%d %B %Y")
    lines = [
        f"🪙 *Gold Rates – {today}*",
        "",
    ]
    for city, karat_rates in rates.items():
        lines.append(f"📍 *{city}*")
        lines.append(f"  • 22K  →  {karat_rates.get('22K', 'N/A')} / gram")
        lines.append(f"  • 24K  →  {karat_rates.get('24K', 'N/A')} / gram")
        lines.append("")

    lines.append("_Source: goodreturns.in_")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# WhatsApp Sender
# ---------------------------------------------------------------------------
class WhatsAppSender:
    """Opens WhatsApp Web and sends messages to the configured contacts."""

    WA_URL = "https://web.whatsapp.com"

    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver
        self.wait = WebDriverWait(driver, 60)

    def open_and_wait_for_login(self):
        """Navigate to WhatsApp Web and wait for the QR scan / auto-login."""
        log.info("Opening WhatsApp Web – scan QR if prompted …")
        self.driver.get(self.WA_URL)

        # Wait until the main chat list is visible (confirms login)
        self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="chat-list"]'))
        )
        log.info("WhatsApp Web ready ✓")

    def send_to_contacts(self, contacts: list[str], message: str):
        for contact in contacts:
            try:
                self._send(contact, message)
                log.info("Message sent to '%s' ✓", contact)
            except Exception as exc:
                log.error("Failed to send to '%s': %s", contact, exc)

    def _send(self, contact: str, message: str):
        # Use the search box to find the contact
        search_box = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[data-testid="search-container"] div[contenteditable]'))
        )
        search_box.clear()
        search_box.send_keys(contact)
        time.sleep(2)

        # Click the first result that matches
        result = self.wait.until(
            EC.element_to_be_clickable((By.XPATH, f'//span[@title="{contact}"]'))
        )
        result.click()
        time.sleep(1)

        # Type the message in the chat input box
        msg_box = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[data-testid="conversation-compose-box-input"]'))
        )
        # Send line-by-line to preserve newlines
        for line in message.split("\n"):
            msg_box.send_keys(line)
            msg_box.send_keys(Keys.SHIFT, Keys.ENTER)

        # Hit Enter to send
        msg_box.send_keys(Keys.ENTER)
        time.sleep(1)

        # Clear search for next contact
        search_box = self.driver.find_element(
            By.CSS_SELECTOR, 'div[data-testid="search-container"] div[contenteditable]'
        )
        search_box.clear()


# ---------------------------------------------------------------------------
# Driver Factory
# ---------------------------------------------------------------------------
def _remove_lock_files(profile_dir: str):
    """
    Remove Chrome lock files that block reuse of a profile directory.
    These are left behind if Chrome crashed or wasn't closed cleanly.
    """
    locks = ["SingletonLock", "SingletonCookie", "SingletonSocket"]
    p = Path(profile_dir)
    for name in locks:
        lock = p / name
        if lock.exists() or lock.is_symlink():
            try:
                lock.unlink()
                log.debug("Removed lock file: %s", lock)
            except OSError as exc:
                log.warning("Could not remove %s: %s", lock, exc)


def build_driver(headless: bool = False, profile_dir: str = "") -> webdriver.Chrome:
    options = Options()

    # ── Windows-specific stability flags ────────────────────────────────────
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--remote-debugging-port=9222")   # fixes DevToolsActivePort error
    options.add_argument("--window-size=1280,900")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    if headless:
        options.add_argument("--headless=new")

    # ── Profile directory (persists WhatsApp login) ──────────────────────────
    if profile_dir:
        # Use an absolute path – relative paths cause issues on Windows
        abs_profile = str(Path(profile_dir).resolve())
        Path(abs_profile).mkdir(parents=True, exist_ok=True)
        _remove_lock_files(abs_profile)
        options.add_argument(f"--user-data-dir={abs_profile}")
        log.info("Using Chrome profile: %s", abs_profile)
    else:
        # Use a temp dir so we never collide with an existing Chrome session
        tmp = tempfile.mkdtemp(prefix="wa_goldrate_")
        options.add_argument(f"--user-data-dir={tmp}")
        log.info("Using temporary Chrome profile: %s", tmp)

    service = Service(ChromeDriverManager().install())

    try:
        driver = webdriver.Chrome(service=service, options=options)
    except SessionNotCreatedException as exc:
        msg = str(exc)
        log.error("Chrome session failed: %s", msg)

        if "DevToolsActivePort" in msg or "user data directory is already in use" in msg:
            log.warning(
                "Profile is locked by another Chrome process.\n"
                "  • Close all Chrome windows and try again, OR\n"
                "  • Set WHATSAPP_PROFILE_DIR = '' in config.py to use a fresh temp profile."
            )
        raise

    return driver


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    log.info("Starting Gold Rate WhatsApp Bot …")
    driver = build_driver(headless=HEADLESS, profile_dir=WHATSAPP_PROFILE_DIR)

    try:
        # ── Step 1: Scrape gold rates ────────────────────────────────────
        log.info("Scraping gold rates for: %s", CITIES)
        scraper = GoldScraper(driver)
        rates = scraper.fetch_rates(CITIES)

        # ── Step 2: Build message ────────────────────────────────────────
        message = build_message(rates)
        log.info("Message preview:\n%s", message)

        # ── Step 3: Send via WhatsApp ────────────────────────────────────
        if not CONTACTS:
            log.warning("No contacts configured in config.py – skipping WhatsApp send.")
        else:
            sender = WhatsAppSender(driver)
            sender.open_and_wait_for_login()
            sender.send_to_contacts(CONTACTS, message)

        log.info("Bot finished successfully.")

    except TimeoutException as exc:
        log.error("Timed out waiting for an element: %s", exc)
    except Exception as exc:
        log.exception("Unexpected error: %s", exc)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
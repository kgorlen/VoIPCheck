"""voipcheck.py -- Check the status of a Rath 2100-VOIP2CS (a.k.a Cisco 191 ATA).

References:
    [Playwright for Python](https://playwright.dev/python/docs/intro)
    [Playwright Python API](https://playwright.dev/python/docs/api/class-playwright)
    [TOML: A config file format for humans](https://toml.io/en/)
    [keyring](https://pypi.org/project/keyring/)
    [Requests: HTTP for Humans](https://docs.python-requests.org/en/master/)
    [Beautiful Soup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
    [Platform Directories](https://pypi.org/project/platformdirs/)
"""

__author__ = "Keith Gorlen"

import sys
from datetime import datetime
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
import tomllib
from typing import Any, NoReturn


SCRIPT_DIR: Path = Path(__file__).absolute().parent
"""Path to directory containing this Python script."""
sys.path.append(str(SCRIPT_DIR))
"""Enable imports from script directory."""

# pylint: disable=wrong-import-position
from __init__ import __version__  # pylint: disable=no-name-in-module
from platformdirs import user_config_dir, user_log_dir
import requests  # type: ignore
import keyring
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup, Tag

# pylint: enable=wrong-import-position


# Global Constants


SCRIPT_NAME: str = Path(__file__).stem
"""Name of this script without .py extension."""
DATE_FMT = "%Y-%m-%d %H:%M:%S"
"""Format for dates in messages."""

# Global Variables

logging.basicConfig(
    handlers=[],
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(SCRIPT_NAME)
"""Logging facility."""
voipcheck_log: Path = (
    Path(user_log_dir("VoIPCheck", appauthor=False, ensure_exists=True)) / "voipcheck.log"
)
"""VoIPCheck log file."""
rotating_handler = RotatingFileHandler(voipcheck_log, maxBytes=5 * 1024 * 1024, backupCount=3)
"""Rotating log file handler."""
rotating_handler.setLevel(logging.INFO)
rotating_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Log format
        datefmt=DATE_FMT,  # Custom date format
    )
)
logging.getLogger().addHandler(rotating_handler)


def exit_with_status(status: int) -> NoReturn:
    """Exit with status.

    Args:
        status (int): exit status
    """
    logger.info(f'{"=" * 60}')
    logging.shutdown()
    sys.exit(status)


def get_voice_status(
    adapter_ip: str, username: str, password: str
) -> dict[str, dict[str, str | None]]:
    """Get status of voice lines from a Rath 2100-VOIP2cs (a.k.a Cisco 191 ATA).

    Args:
        adapter_ip: str IP address of VoIP adapter.
        username: str Username for login.
        password: str Password for login.

    Raises:
        ValueError: Login failed.
        ValueError: Failed to retrieve outerHTML from the information element.
        LookupError: Error getting voice status.

    Returns:
        dict[str, dict[str, str | None]]: Parsed voice status data.
    """
    try:
        with sync_playwright() as p:
            logger.info("Starting Playwright browser ...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            logger.info(f"Opening http://{adapter_ip}/ ...")
            page.goto(f"http://{adapter_ip}/", timeout=30000)

            logger.info('Wait for the "user" field to be present ...')
            page.wait_for_selector('input[name="user"]')

            # Find and fill username field
            page.fill('input[name="user"]', username)

            # Find and fill password field
            page.fill('input[name="pwd"]', password)

            logger.info(f"Logging in as {username} ...")
            page.press('input[name="pwd"]', "Enter")

            logger.info("Waiting for login to finish ...")
            page.wait_for_selector('#trt_quicksetup\\.asp', timeout=30000)

            # Check if login successful
            if page.url == f"http://{adapter_ip}/":
                raise ValueError("Login failed.")

            logger.info(f"Navigating to status page http://{adapter_ip}/voice.asp ...")
            page.goto(f"http://{adapter_ip}/voice.asp", timeout=30000)

            logger.info("Waiting for iframe to be present ...")
            page.wait_for_selector("#iframe")

            logger.info("Switching to iframe ...")
            frame = page.frame(name="iframe")
            if not frame:
                raise ValueError("Failed to switch to iframe.")

            logger.info('Waiting for element with id "information" to be present ...')
            frame.wait_for_selector("#Information")

            # Find the element with id 'information'
            information_element = frame.query_selector("#Information")
            if not information_element:
                raise ValueError("Failed to retrieve the information element.")

            logger.info("Parsing HTML content ...")
            outer_html = information_element.inner_html()
            if outer_html is None:
                raise ValueError("Failed to retrieve outerHTML from the information element.")
            soup = BeautifulSoup(outer_html, "html.parser")

            # Loop over tr elements and extract key-value pairs
            data: dict[str, dict[str, str | None]] = {}
            for row in soup.find_all("tr"):
                assert isinstance(row, Tag)
                tds = row.find_all("td")
                if len(tds) == 1:
                    if key := tds[0].get_text(strip=True):
                        data[key] = {}
                else:
                    for i, td in enumerate(tds):
                        assert isinstance(td, Tag)
                        if td.get("align") == "left":
                            data[key][td.get_text(strip=True)] = (
                                tds[i + 1].get_text(strip=True) if i + 1 < len(tds) else None
                            )

            browser.close()  # Close the browser
            return data

    except Exception as e:
        raise LookupError(f"Error getting voice status: {e}") from e


def main() -> None:
    """Read configuration file, get voice status, and send pings.

    Raises:
        FileNotFoundError: Configuration file not found.
        ValueError: Error reading configuration file.
        KeyError: Key not found in configuration file.
        LookupError: Password not found.
    """
    logger.info(f'{"=" * 60}')
    logger.info(f"{SCRIPT_NAME} version {__version__} starting ...")

    config_file: Path = (
        Path(user_config_dir("VoIPCheck", appauthor=False, roaming=True)) / "voipcheck.toml"
    )
    """User-specific configuration file."""

    config_data: dict[str, Any]
    """Data from voipcheck.toml file."""

    if not config_file.exists():
        raise FileNotFoundError(f'Configuration file not found: "{config_file}"')

    try:
        with config_file.open("rb") as f:
            config_data = tomllib.load(f)
    except Exception as e:
        raise ValueError(
            f"Error reading configuration file {
                            config_file}: {e}"
        ) from e

    logger.info(f'Configuration loaded from "{config_file}".')

    for key in ("adapter_ip", "service", "username", "registration_state_ping_url"):
        if key not in config_data:
            raise KeyError(f'"{key}" not found in {config_file}')

    for line in ("line1", "line2"):
        if line not in config_data:
            raise KeyError(f'"{line}" not found in {config_file}')
        for key in ("hook_state_ping_url",):
            if key not in config_data[line]:
                raise KeyError(f'"{key}" not found in {config_file}')

    adapter_ip: str = config_data["adapter_ip"]
    service: str = config_data["service"]
    username: str = config_data["username"]

    logger.info(f"Getting password for {service} {username} ...")
    password = keyring.get_password(service, username)
    if password is None:
        raise LookupError(f"2100-VOIP2CS {username} password not found.")

    data = get_voice_status(adapter_ip, username, password)

    for l in range(1, 3):
        line = f"Line {l} Status"
        logger.info(f"{line}")
        for attr in ("Hook State:", "Registration State:"):
            logger.info(f"\t{attr} {data[line][attr]}")

    for l in range(1, 3):
        if data[f"Line {l} Status"]["Hook State:"] == "On":
            logger.info(f"Pinging healthchecks.io Line {l} Hook State On ...")
            response = requests.get(config_data[f"line{l}"]["hook_state_ping_url"], timeout=20)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx, 5xx)
            logger.info("Successful Hook State ping sent.")

    unregistered: list[str] = [
        f"Line {l}"
        for l in range(1, 3)
        if data[f"Line {l} Status"]["Registration State:"] != "Registered"
    ]

    if not unregistered:
        logger.info("Pinging healthchecks.io Registration State OK ...")
        response = requests.get(config_data["registration_state_ping_url"], timeout=20)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx, 5xx)
        logger.info("Successful Registration State ping sent.")
    else:
        msg = f'{", ".join(unregistered)} NOT REGISTERED.'
        logger.info(f'Sending fail ping: "{msg}" ...')
        response = requests.post(
            config_data["registration_state_ping_url"] + "/fail", timeout=20, data=msg
        )
        response.raise_for_status()  # Raise an exception for bad status codes (4xx, 5xx)
        logger.info("Fail ping sent.")
        exit_with_status(1)

    exit_with_status(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as msg:  # pylint: disable=broad-exception-caught
        """Log a CRITICAL message and sys.exit(1)."""
        print(
            f"{datetime.now().strftime(DATE_FMT)} - CRITICAL - {msg}; exiting.",
            file=sys.stderr,
        )
        logger.critical(f"{msg}; exiting.")
        exit_with_status(1)

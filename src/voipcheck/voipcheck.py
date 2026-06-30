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
import os
import subprocess
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

# ruff: disable[E402]  # Disables module-import-not-at-top-of-file warnings
# pylint: disable=wrong-import-position

from __init__ import __version__  # pylint: disable=no-name-in-module
from platformdirs import user_config_dir, user_log_dir
import keyring
from playwright.sync_api import (
    Playwright,
    sync_playwright,
    Browser,
    BrowserContext,
    Page,
    ElementHandle,
)
from bs4 import BeautifulSoup, Tag

# ruff: enable[E402]  # Enables module-import-not-at-top-of-file warnings
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
rotating_handler = RotatingFileHandler(voipcheck_log, maxBytes=10_000_000, backupCount=19)
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


def ping_healthchecks(url: str, data: str = "", timeout=10) -> None:
    """Send ping to healthchecks.io: https://healthchecks.io/docs/.

    Arguments:
                url -- healthchecks.io URL with unique ping code
                data -- optional data to include in the ping
                timeout -- timeout for the ping request (default: 10 seconds)
    Raises:
                RuntimeError -- if the ping fails
                OSError -- if curl is not found
    """
    cmd = [
        "curl",
        "-fsS",
        "--max-time",
        str(timeout),
        "--retry",
        "5",
        "-o",
        "NUL" if os.name == "nt" else "/dev/null",
    ]
    if data:
        cmd += ["--data-raw", data]
    # cmd.append("http://this-hostname-should-not-exist.invalid")  # Test DNS failure
    # cmd.append("https://10.255.255.1") # For testing, simulates a 504 Gateway Timeout
    cmd.append(url)
    logger.info(f"Pinging healthchecks.io with command: {' '.join(cmd)} ...")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        err = result.stderr

        if result.returncode != 0:
            raise RuntimeError(f"{' '.join(cmd)} failed: {err.strip()}")

    except OSError as e:
        raise OSError(f"curl not found or error: {e}")  # pylint: disable=raise-missing-from


def signal_failure(url: str, msg: str) -> NoReturn:
    """Signal failure and exit.

    Args:
        url (str): healthchecks.io URL
        msg (str): message to log
    """
    logger.info(f"Signaling failure to {url}, data='{msg}' ...")
    try:
        ping_healthchecks(url + "/fail", msg)
    except (RuntimeError, OSError) as e:
        logger.critical(f"Failed to ping {url}: {e}")
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.critical(f"Unexpected error pinging {url}: {type(e).__name__}: {e}")
    print(f"{datetime.now().strftime(DATE_FMT)} - CRITICAL - {msg}; exiting.", file=sys.stderr)
    logger.critical(f"{msg}; exiting.")
    exit_with_status(1)


class VoIPAdapter:
    """Class representing a VoIP adapter."""

    def __init__(self, adapter_url: str, username: str, password: str) -> None:
        """Initialize VoIPAdapter instance.

        Args:
            adapter_url (str): URL of VoIP adapter.
            username (str): Username for login.
            password (str): Password for login.
        """
        self.adapter_url: str = adapter_url
        """URL of VoIP adapter management interface."""
        self.username: str = username
        """Username for login."""
        self.password: str = password
        """Password for login."""
        self.pw: Playwright | None = None
        """Playwright instance."""
        self.browser: Browser | None = None
        """Playwright browser instance."""
        self.context: BrowserContext
        """Playwright browser context."""
        self.page: Page
        """Playwright page instance."""

    def __enter__(self) -> "VoIPAdapter":
        """Enter context manager.

        Raises:
            ValueError: Login failed.
            Exception: Error connecting to VoIP adapter.
        Returns:
            VoIPAdapter: if login successful."""

        try:
            logger.info("Starting Playwright browser ...")
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.launch(headless=True)
            self.context = self.browser.new_context()
            self.page = self.context.new_page()

            logger.info(f"Opening {self.adapter_url} ...")
            self.page.goto(self.adapter_url, timeout=30000)

            logger.info('Wait for the "user" field to be present ...')
            self.page.wait_for_selector('input[name="user"]')

            # Find and fill username field
            self.page.fill('input[name="user"]', self.username)

            # Find and fill password field
            self.page.fill('input[name="pwd"]', self.password)

            logger.info(f"Logging in as {self.username} ...")
            self.page.press('input[name="pwd"]', "Enter")

            logger.info("Waiting for login to finish ...")
            self.page.wait_for_selector("#trt_quicksetup\\.asp", timeout=30000)
            logger.info("Login successful.")

            # Check if login successful
            if self.page.url == self.adapter_url:
                raise ValueError("Login failed.")

            return self

        except Exception as e:
            logger.error(
                f"Error connecting to VoIP adapter {self.adapter_url}: {type(e).__name__}: {e}"
            )
            raise

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Logout and close browser."""
        if self.browser:
            self.logout_and_close()
        if self.pw:
            self.pw.stop()

    def parse_html_table(
        self, element_id: str, element: ElementHandle
    ) -> dict[str, dict[str, str | None]]:
        """Parse HTML table in the information element and return data as a dictionary.

        Args:
            element_id (str): ID of the element containing the HTML table to parse.
            element (ElementHandle): Playwright ElementHandle for the element
            containing the HTML table.

        Returns:
                dict[str, dict[str, str | None]]: Parsed table data.
        Raises:
            ValueError: Failed to retrieve the information element.
            ValueError: Failed to retrieve outerHTML from the information element.
        """
        logger.info(f"Parsing HTML content for {element_id} ...")

        outer_html = element.inner_html()
        if outer_html is None:
            raise ValueError("Failed to retrieve outerHTML from the information element.")
        soup = BeautifulSoup(outer_html, "html.parser")

        # Loop over tr elements and extract key-value pairs
        data: dict[str, dict[str, str | None]] = {}
        """data["Line {l} Status"]"""
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
                        # Will raise NameError if "Line {l} Status" section header missing
                        data[key][td.get_text(strip=True)] = (  # type: ignore[assignment]
                            tds[i + 1].get_text(strip=True) if i + 1 < len(tds) else None
                        )

        logger.info(f"HTML content for {element_id} parsed successfully.")
        return data

    def get_voice_status(self) -> dict[str, dict[str, str | None]]:
        """Get status of voice lines from a Rath 2100-VOIP2cs (a.k.a Cisco 191 ATA).

        Args:
            adapter_url: str URL of VoIP adapter.
            username: str Username for login.
            password: str Password for login.

        Raises:
            ValueError: Login failed.
            ValueError: Failed to retrieve outerHTML from the information element.
            Exception: Error getting voice status.

        Returns:
            dict[str, dict[str, str | None]]: Parsed voice status data.
        """
        try:
            logger.info(f"Navigating to Voice page {self.adapter_url}/voice.asp ...")
            self.page.goto(f"{self.adapter_url}/voice.asp", timeout=30000)

            logger.info("Waiting for iframe to be present ...")
            self.page.wait_for_selector("#iframe")

            logger.info("Switching to iframe ...")
            frame = self.page.frame(name="iframe")
            if not frame:
                raise ValueError("Failed to switch to iframe.")

            logger.info('Waiting for element with id "information" to be present ...')
            frame.wait_for_selector("#Information")

            logger.info('Querying frame for element id: "#Information" ...')
            info_element: ElementHandle | None = frame.query_selector("#Information")
            if not info_element:
                raise ValueError(f'Failed to retrieve the information element "{"#Information"}".')

            return self.parse_html_table("#Information", info_element)

        except Exception as e:
            logger.error(f"Error getting voice status: {type(e).__name__}: {e}")
            raise

    def get_mem_info(self) -> dict[str, int]:
        """Get free and total memory from Status tab Memory Information.

        Raises:
            ValueError: Failed to parse memory information data.
            KeyError: Required key not found in memory information.
            Exception: Error getting memory information.

        Returns:
            dict[str, int]: Dictionary with 'MemFree:' and 'MemTotal' values.
        """
        try:
            logger.info(
                f"Navigating to Memory Information page "
                f"{self.adapter_url}/Memory_Information.asp ..."
            )
            self.page.goto(f"{self.adapter_url}/Memory_Information.asp", timeout=30000)

            logger.info("Waiting for Memory Information to load ...")
            self.page.wait_for_selector(".CONTENT_GROUP")

            rows = self.page.locator(
                ".CONTENT_GROUP tr.TABLECONTENT_S, .CONTENT_GROUP tr.TABLECONTENT_D"
            )
            data: dict[str, int] = {}

            for i in range(rows.count()):
                cols = rows.nth(i).locator("td")
                key = cols.nth(0).text_content()
                if not key:
                    continue

                value = cols.nth(1).text_content()
                if not value:
                    logger.warning(f"No value for {key}; skipping.")
                    continue

                data[key.split(":")[0]] = int(value.split()[0])

            if not data:
                raise ValueError("Failed to parse memory information data.")

            for key in ("MemFree", "MemTotal"):
                if key not in data:
                    raise KeyError(f"Required key not found in memory information: {key}")

            return data

        except Exception as e:
            logger.error(f"Error getting memory information: {type(e).__name__}: {e}")
            raise

    def reboot(self) -> NoReturn:
        """Reboot the VoIP adapter.

        Raises:
            Exception: Error rebooting VoIP adapter.
        """
        try:
            logger.info(f"Navigating to Reboot page {self.adapter_url}/Reboot.asp ...")
            self.page.goto(f"{self.adapter_url}/Reboot.asp", timeout=30000)
            logger.info('Waiting for "Reboot" button to be present ...')
            self.page.get_by_role("button", name="Reboot").wait_for()
            logger.info("Setting up dialog handler to confirm reboot ...")
            self.page.once("dialog", lambda dialog: dialog.accept())
            logger.info('Clicking on "Reboot" button ...')
            self.page.get_by_role("button", name="Reboot").click()
            logger.info("Reboot initiated.")
            exit_with_status(0)

        except Exception as e:
            logger.error(f"Error rebooting VoIP adapter: {type(e).__name__}: {e}")
            raise

    def logout_and_close(self) -> None:
        """Logout and close browser."""
        if self.browser:
            try:
                logger.info("Logging out ...")
                self.page.get_by_role("link", name="Log Out").click()
                self.page.wait_for_selector('input[name="user"]')

                logger.info("Logout OK, closing browser ...")
                self.browser.close()  # Close the browser
                self.browser = None  # Remove reference to browser

            except Exception as e:
                logger.error(f"Error cleaning up Playwright resources: {type(e).__name__}: {e}")
                raise


def load_config() -> dict[str, Any]:
    """Load configuration from voipcheck.toml file.
    Raises:
        FileNotFoundError: Configuration file not found.
        ValueError: Error reading configuration file.
        KeyError: Key not found in configuration file.
    Returns:
        dict[str, Any]: Configuration data. Expected keys: adapter_url, service,
        username, adapter_ping_url, registration_state_ping_url, line1, line2
        (each with hook_state_ping_url).
    """
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
        raise ValueError(f"Error reading configuration file {config_file}: {e}") from e

    logger.info(f'Configuration loaded from "{config_file}".')

    for key in (
        "adapter_url",
        "service",
        "username",
        "adapter_ping_url",
        "registration_state_ping_url",
        "free_memory_threshold_kB",
    ):
        if key not in config_data:
            raise KeyError(f'"{key}" not found in {config_file}')

    for line in ("line1", "line2"):
        if line not in config_data:
            raise KeyError(f'"{line}" not found in {config_file}')
        for key in ("hook_state_ping_url",):
            if key not in config_data[line]:
                raise KeyError(f'"{key}" not found in {config_file}')

    return config_data


def check_voice_status(
    config_data: dict[str, Any], voice_data: dict[str, dict[str, str | None]]
) -> int:
    """Check voice status and send pings to healthchecks.io.

    Args:
        config_data (dict[str, Any]): Configuration data.
        voice_data (dict[str, dict[str, str | None]]): Voice status data.

    Returns:
        int: Exit status 0 if all lines registered, 1 if any line not registered.

    Raises:
        RuntimeError: If pinging healthchecks.io fails.
    """
    for ln in range(1, 3):
        line = f"Line {ln} Status"
        logger.info(f"{line}")
        for attr in ("Hook State:", "Registration State:"):
            logger.info(f"\t{attr} {voice_data[line][attr]}")

    for ln in range(1, 3):
        if voice_data[f"Line {ln} Status"]["Hook State:"] == "On":
            logger.info(f"Pinging healthchecks.io Line {ln} Hook State On ...")
            ping_healthchecks(config_data[f"line{ln}"]["hook_state_ping_url"])
            logger.info("Successful Hook State ping sent.")

    unregistered: list[str] = [
        f"Line {ln}"
        for ln in range(1, 3)
        if voice_data[f"Line {ln} Status"]["Registration State:"] != "Registered"
    ]

    if unregistered:
        msg = f'{", ".join(unregistered)} NOT REGISTERED.'
        logger.info(f'Sending fail ping: "{msg}" ...')
        ping_healthchecks(config_data["registration_state_ping_url"] + "/fail", msg)
        logger.info("Fail ping sent.")
        return 1

    logger.info("Pinging healthchecks.io Registration State OK ...")
    ping_healthchecks(config_data["registration_state_ping_url"])
    logger.info("Successful Registration State ping sent.")
    return 0


def main() -> None:
    """Read configuration file, get voice status, and send pings.

    Raises:
        FileNotFoundError: Configuration file not found.
        ValueError: Error reading configuration file.
        KeyError: Key not found in configuration file.
        LookupError: Password not found.

    Note:
        Logging in and accessing the Voice status page causes a memory leak
        under Firmware version 11-2-3MPP0001-028 Oct 24 2022. This exhausts
        memory after about 10,000 cycles, causing the adapter to fail in various
        ways.  Adapter power must then be cycled manually to restart the
        adapter. To avoid this, the adapter is rebooted if free memory is less
        than `free_memory_threshold_kB` kB.

    """
    logger.info(f'{"=" * 60}')
    logger.info(f"{SCRIPT_NAME} version {__version__} starting ...")

    config_data: dict[str, Any] = load_config()
    """Data from voipcheck.toml file."""
    adapter_url: str = config_data["adapter_url"]
    """URL of VoIP adapter management interface."""
    service: str = config_data["service"]
    """Service name for password lookup."""
    username: str = config_data["username"]
    """Username for password lookup."""
    voice_data: dict[str, dict[str, str | None]]
    """Voice status data."""
    mem_info: dict[str, int]
    """Total and free Memory in kB."""
    exit_status: int
    """Exit status: 0 if all lines registered, 1 if any line not registered."""
    reboot_threshold: int = config_data["free_memory_threshold_kB"]
    """Free memory threshold in kB for rebooting adapter."""

    logger.info(f"Getting password for {service} {username} ...")
    password: str | None = keyring.get_password(service, username)
    if password is None:
        raise LookupError(f"2100-VOIP2CS {username} password not found.")

    try:
        with VoIPAdapter(adapter_url, username, password) as adapter:
            voice_data = adapter.get_voice_status()
            exit_status = check_voice_status(config_data, voice_data)
            mem_info = adapter.get_mem_info()

            if voice_data["System Status"]["Elapsed Time:"]:
                logger.info(f"Elapsed Time: {voice_data['System Status']['Elapsed Time:']}")

            logger.info(
                f"MemTotal: {mem_info['MemTotal']} kB, MemFree: {mem_info['MemFree']} kB, "
                f"Reboot threshold: {reboot_threshold} kB"
            )

            if mem_info["MemFree"] < reboot_threshold:
                logger.warning(f"Free memory is < {reboot_threshold} kB; rebooting adapter ...")
                adapter.reboot()

    except Exception as e:  # pylint: disable=broad-exception-caught
        signal_failure(config_data["adapter_ping_url"], str(e))

    exit_with_status(exit_status)


def cli() -> None:
    """Command line interface for voipcheck.py."""
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


if __name__ == "__main__":
    cli()

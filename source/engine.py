import AO3
import configparser
import hashlib
import logging
import os
import sys

from pathlib import Path
from AO3 import GuestSession, Session, Work
from typing import Dict

from . import constants

LOG = logging.getLogger(__name__)


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


class Engine:
    base_dir: Path
    downloads_dir: Path
    filetype = str
    config: configparser.ConfigParser
    session: GuestSession

    def __init__(self, cwd):
        self.base_dir = Path(cwd)
        LOG.info(f"Current working directory: {self.base_dir}")
        self.config = self._parse_configuration()
        self._login()
        self._make_directories()

    def _parse_configuration(self) -> configparser.ConfigParser:
        configuration_file = self.base_dir / constants.CONFIGURATION_FILE
        LOG.info(f"Parsing configuration file at: {configuration_file}")

        config = configparser.ConfigParser()
        config.read(configuration_file)

        if "downloads" in config and "directory" in config["downloads"]:
            self.downloads_dir = Path(config["downloads"]["directory"])
        else:
            self.downloads_dir = self.base_dir / constants.DEFAULT_DOWNLOADS_DIR

        if "downloads" in config and "filetype" in config["downloads"]:
            filetype = config["downloads"]["filetype"].upper()
            if filetype.upper() not in constants.VALID_FILETYPES:
                valid_filetypes_string = ", ".join(constants.VALID_FILETYPES)
                LOG.error(
                    f"Invalid filetype specified in {configuration_file}, "
                    f"valid types are: {valid_filetypes_string}. Please fix "
                    f"the configuration file and rerun."
                )
                exit(1)
            self.filetype = filetype
        else:
            self.filetype = constants.DEFAULT_DOWNLOADS_FILETYPE
        LOG.info(f"Download filetype set to: {self.filetype}")

        LOG.info(f"Current downloads directory: {self.downloads_dir.resolve()}")

        return config

    def _login(self) -> None:
        if not (
            "credentials" in self.config
            and "username" in self.config["credentials"]
            and "password" in self.config["credentials"]
        ):
            LOG.warning(
                f"No credentials were specified in "
                f"{constants.CONFIGURATION_FILE}. Proceeding with guest "
                f"session. Note that bookmarks feature will not work in "
                f"guest mode."
            )
            self.session = GuestSession()
            return

        username = self.config["credentials"]["username"]
        password = self.config["credentials"]["password"]
        try:
            self.session = Session(username, password)
            self.session.user.reload()
            LOG.info(f"Authenticated as user: {self.session.username}")
        except AO3.utils.LoginError:
            LOG.error(
                "Invalid username or password. Please check your "
                "credentials are correct in the configuration file."
            )
            exit(1)

    def _make_directories(self) -> None:
        LOG.info("Validating directory structure...")
        data_dir = self.base_dir / constants.DATA_DIR / self.session.username
        data_dir.mkdir(parents=True, exist_ok=True)
        bookmarks_dir = data_dir / constants.BOOKMARKS_DIR
        bookmarks_dir.mkdir(parents=True, exist_ok=True)
        downloads_dir = self.downloads_dir / self.session.username
        downloads_dir.mkdir(parents=True, exist_ok=True)

    def _get_existing_chapters_file(self, work: Work) -> Path:
        if not work.loaded:
            work.reload()
        return (
            self.base_dir
            / constants.DATA_DIR
            / self.session.username
            / constants.BOOKMARKS_DIR
            / (work.title + ".chapters")
        )

    def _get_download_file_path(self, work: Work) -> Path:
        if not work.loaded:
            work.reload()
        return (
            self.downloads_dir
            / self.session.username
            / (work.title + "." + self.filetype.lower())
        )

    def _get_existing_chapters(self, work: Work) -> Dict[str, str]:
        filename = self._get_existing_chapters_file(work)
        try:
            return dict(line.strip().split("\t") for line in open(filename))
        except FileNotFoundError:
            LOG.info(f"No existing chapters exist for work: {work.title}")
        except Exception:
            LOG.warning(f"Unspecified error occurred trying to open file: {filename}")
        return set()

    def _download_work(self, work: Work) -> None:
        filename = self._get_download_file_path(work)
        print(f"Downloading {work.title} to: {filename}")
        if not work.loaded:
            work.reload()
        work.download_to_file(filename, self.filetype)

    def _update_existing_chapters(self, work: Work, chapters: Dict[str, str]) -> None:
        filename = self._get_existing_chapters_file(work)
        with open(filename, "w") as f:
            f.write("\n".join(f"{k}\t{v}" for k, v in chapters.items()))
        LOG.info(f"Successfully updated chapters for work: {work.title}")

    def _check_for_new_chapters(self, work: Work) -> None:
        LOG.info(f"Checking for updates for {work.title}")
        if not work.loaded:
            work.reload()
        current_chapters = {
            chapter.title: md5(chapter.text) for chapter in work.chapters
        }
        existing_chapters = self._get_existing_chapters(work)
        if current_chapters != existing_chapters:
            LOG.info(f"Found changes in chapters for work: {work.title}")
            self._download_work(work)
            self._update_existing_chapters(work, current_chapters)
        else:
            LOG.info(f"No changes found in chapters for work: {work.title}")

    def _check_for_updates_to_bookmarks(self) -> None:
        LOG.info("Getting bookmarks...")
        # TODO: send PR to AO3 API to make this work for series bookmarks
        for work in self.session.get_bookmarks():
            self._check_for_new_chapters(work)

    def run(self) -> None:
        if isinstance(self.session, Session):
            self._check_for_updates_to_bookmarks()
        else:
            LOG.info("Skipping checking bookmarks since session is a guest session.")

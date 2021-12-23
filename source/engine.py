import AO3
import configparser
import hashlib
import logging
import os
import sys
import time

from pathlib import Path
from AO3 import GuestSession, Session, Work
from typing import Dict, List, Set

from . import constants

LOG = logging.getLogger(__name__)


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


class Engine:
    base_dir: Path
    downloads_dir: Path
    filetype = str
    session: GuestSession
    use_threading = bool
    config: configparser.ConfigParser

    _works: Dict[int, Work] = {}
    _changed_works: Dict[int, Dict[str, str]] = {}

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

        if "engine" in config and "threading" in config["engine"]:
            self.use_threading = config["engine"]["threading"]
        else:
            self.use_threading = False
        LOG.info(f"Use threading: {self.use_threading}")

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

    def _get_chapter_hashes_file(self, work: Work) -> Path:
        return (
            self.base_dir
            / constants.DATA_DIR
            / self.session.username
            / constants.BOOKMARKS_DIR
            / (f"{work.id}.chapters")
        )

    def _get_download_file_path(self, work: Work) -> Path:
        return (
            self.downloads_dir
            / self.session.username
            / (f"{work.id} - {work.title}.{self.filetype.lower()}")
        )

    def _get_existing_chapter_hashes(self, work: Work) -> Dict[str, str]:
        filename = self._get_chapter_hashes_file(work)
        try:
            return dict(line.strip().split("\t") for line in open(filename))
        except FileNotFoundError:
            LOG.info(f"No saved chapter hashes for work: {work.id} - {work.title}")
        except Exception:
            LOG.warning(f"Unspecified error occurred trying to open file: {filename}")
        return set()

    @AO3.threadable.threadable
    def _check_for_changed_chapters(self, work: Work) -> None:
        LOG.info(f"Checking for changes in {work.id} - {work.title}")
        current_chapters = {
            chapter.title: md5(chapter.text) for chapter in work.chapters
        }
        existing_chapters = self._get_existing_chapter_hashes(work)
        if current_chapters != existing_chapters:
            LOG.info(f"Found changes in chapters for work: {work.id} - {work.title}")
            self._changed_works[work.id] = current_chapters
        else:
            LOG.info(f"No changes found in chapters for work: {work.id} - {work.title}")

    @AO3.threadable.threadable
    def _download_work(self, work: Work) -> None:
        filename = self._get_download_file_path(work)
        LOG.info(f"Downloading {work.id} - {work.title} to: {filename}")
        work.download_to_file(filename, self.filetype)

    @AO3.threadable.threadable
    def _update_chapter_hashes(self, work: Work) -> None:
        chapters = self._changed_works[work.id]
        filename = self._get_chapter_hashes_file(work)
        with open(filename, "w") as f:
            f.write("\n".join(f"{k}\t{v}" for k, v in chapters.items()))
        LOG.info(f"Updated chapter hashes for work: {work.id} - {work.title}")

     
    def _load_works(self, works: List[Work]):
        start = time.time()
        if self.use_threading:
            threads = []
            for work in works:
                self._works[work.id] = work    
                threads.append(work.reload(threaded=True))
            for thread in threads:
                thread.join()
        else:
            for work in works:
                self._works[work.id] = work
                work.reload()
        LOG.info(f"(PERF) Loaded {len(works)} works in {round(time.time() - start, 5)}s.")

    def _check_for_updates(self, works: List[Work]):
        start = time.time()
        if self.use_threading:
            threads = []
            for work in works:
                threads.append(self._check_for_changed_chapters(work, threaded=True))
            for thread in threads:
                thread.join()
        else:
            for work in works:
                self._check_for_changed_chapters(work)
        LOG.info(f"(PERF) Checked for updates in {len(works)} works in {round(time.time()-start, 5)}s.")

    def _download_updated_works(self):
        start = time.time()
        if self.use_threading:
            threads = []
            for work_id in self._changed_works:
                if work_id in self._works:
                    threads.append(self._download_work(self._works[work_id], threaded=True))
            for thread in threads:
                thread.join()
        else:
            for work_id in self._changed_works:
                if work_id in self._works:
                    self._download_work(self._works[work_id])
        LOG.info(f"(PERF) Downloaded {len(self._changed_works)} works in {round(time.time()-start, 5)}s.")


    def _update_works_on_disk(self):
        start = time.time()
        if self.use_threading:
            threads = []
            for work_id in self._changed_works:
                if work_id in self._works:
                    threads.append(self._update_chapter_hashes(self._works[work_id], threaded=True))
            for thread in threads:
                thread.join()
        else:
            for work_id in self._changed_works:
                if work_id in self._works:
                    self._update_chapter_hashes(self._works[work_id])
        LOG.info(f"(PERF) Updated {len(self._changed_works)} works on disk in {round(time.time()-start, 5)}s.")
        self._changed_works = {}


    def _check_and_download_updated_bookmarks(self) -> None:
        LOG.info("Loading bookmarked works...")

        start = time.time()
        # TODO: send PR to AO3 API to make this work for series bookmarks
        bookmarks = self.session.get_bookmarks(use_threading=self.use_threading)
        LOG.info(f"(PERF) Got {len(bookmarks)} bookmarks in {round(time.time() - start, 5)}s.")

        self._load_works(bookmarks)
        self._check_for_updates(bookmarks)
        self._download_updated_works()
        self._update_works_on_disk()
        

    def run(self) -> None:
        if isinstance(self.session, Session):
            self._check_and_download_updated_bookmarks()
        else:
            LOG.info("Skipping checking bookmarks since session is a guest session.")

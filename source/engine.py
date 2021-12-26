import AO3
import logging
import os
import sys
import time

from pathlib import Path
from AO3 import GuestSession, Session, Work
from slugify import slugify
from threading import Semaphore
from typing import Any, Callable, Dict, List, Optional, Set

from . import constants
from .configuration import Configuration

LOG = logging.getLogger(__name__)


class Engine:
    base_dir: Path
    config: Configuration
    session: GuestSession

    _works: Dict[int, Work] = {}
    _downloaded: Dict[int, Path] = {}

    _thread_limiter: Optional[Semaphore] = None

    def __init__(self, cwd: str):
        self.base_dir = Path(cwd)
        LOG.info(f"Current working directory: {self.base_dir}")

        # Validate data directory structure
        data_dir = self.base_dir / constants.DATA_DIR
        data_dir.mkdir(parents=True, exist_ok=True)

        # Set default configuration values
        self.session = GuestSession()
        self.config = Configuration(self.base_dir / constants.CONFIGURATION_FILE)
        self.get_settings()

        if self.config.username and self.config.password:
            self.login(self.config.username, self.config.password)

        if self.config.should_rate_limit:
            AO3.utils.limit_requests()

        if self.config.should_use_threading and self.config.concurrency_limit > 1:
            self._thread_limiter = Semaphore(value=self.config.concurrency_limit)

    def login(self, username: str, password: str) -> int:
        try:
            self.session = Session(username, password)
            self.session.refresh_auth_token()
            LOG.info(f"Authenticated as user: {self.session.username}")
            data_dir = self.base_dir / constants.DATA_DIR / self.session.username
            data_dir.mkdir(parents=True, exist_ok=True)
            return 0
        except AO3.utils.LoginError:
            LOG.error("Invalid username or password.")
            return 1

    def logout(self) -> int:
        try:
            del self.session
            self.session = GuestSession()
            LOG.info("Logged out.")
            return 0
        except Exception:
            LOG.error("Error logging out.")
            return 1

    def get_settings(self) -> int:
        try:
            self.config.parse_from_file()
            return 0
        except Exception:
            LOG.error(f"Error getting settings: {e}")
            return 1

    def update_settings(
        self,
        username: str,
        password: str,
        downloads_dir: Path,
        filetype: str,
        should_use_threading: bool,
        concurrency_limit: int,
        should_rate_limit: bool,
    ) -> int:
        self.config.username = username
        self.config.password = password
        self.config.downloads_dir = downloads_dir
        self.config.filetype = filetype
        self.config.should_use_threading = should_use_threading
        self.config.concurrency_limit = concurrency_limit
        self.config.should_rate_limit = should_rate_limit

        return self.config.write_to_file()

    def is_authed(self) -> bool:
        return self.session.is_authed

    def remove(self, work_id: int) -> bool:
        if work_id in self._works:
            del self._works[work_id]
        if work_id in self._downloaded:
            del self._downloaded[work_id]

    def work_urls_to_work_ids(self, urls: Set[str]) -> Set[int]:
        ids = set()
        for url in urls:
            try:
                work_id = AO3.utils.workid_from_url(url)
                if work_id:
                    ids.add(work_id)
            except Exception as e:
                LOG.error(f"Error getting work id from URL {url}: {e}. " f"Skipping.")
        return ids

    def get_bookmark_ids(self) -> Set[int]:
        LOG.info("Loading bookmarked works...")
        # TODO: send PR to AO3 API to make this work for series bookmarks
        ids = set()
        bookmarks = self.session.get_bookmarks(
            use_threading=self.config.should_use_threading
        )
        for work in bookmarks:
            if work.id not in self._works:
                self._works[work.id] = work
                ids.add(work.id)
            else:
                LOG.info(
                    f"Bookmarked work with id {work.id} was already loaded, "
                    f"skipping."
                )
        return ids

    def _load_work_with_current_session(self, work_id: int) -> None:
        if work_id in self._works and self._works[work_id].loaded:
            LOG.info(f"Work id {work_id} was already loaded, skipping.")
            return

        try:
            work = Work(work_id, load=False)
            work.set_session(self.session)
            # TODO: determine whether load_chapters=False is useful here.
            work.reload()
            LOG.info(f"Loaded work id {work.id}.")
            self._works[work.id] = work
        except AttributeError:
            # This is a hack due to how the AO3 API works right now.
            LOG.warning(f"Work {work_id} is only accessible to logged-in users.")
            raise AO3.utils.AuthError("Work is only accessible to logged-in users.")

    def _acquire_semaphore(self):
        if self._thread_limiter:
            self._thread_limiter.acquire()

    def _release_semaphore(self):
        if self._thread_limiter:
            self._thread_limiter.release()

    @AO3.threadable.threadable
    def _load_work(
        self,
        work_id: int,
        callback: Callable[[int, Dict[str, Any], Optional[str]], None],
    ) -> None:
        while True:
            wait_time = constants.INITIAL_WAIT_TIME_IN_SECONDS
            self._acquire_semaphore()
            try:
                self._load_work_with_current_session(work_id)
                callback(work_id, data={"work": self._works[work_id]})
                self._release_semaphore()
                return
            except AO3.utils.HTTPError:
                LOG.warning(
                    f"Hit rate limit trying to load work {work_id}, "
                    f"trying again in {wait_time}s."
                )
                callback(
                    work_id,
                    data={"show_loading": True},
                    error_message=(
                        f"Hit rate limit, trying again " f"in {wait_time}s..."
                    ),
                )
                self._release_semaphore()
                time.sleep(wait_time)
                wait_time *= 2
            except Exception as e:
                LOG.error(f"Error loading work id {work_id}: {e}. Skipping.")
                callback(work_id, error_message=str(e))
                self._release_semaphore()
                return

    def load_works(
        self,
        work_ids: Set[int],
        callback: Callable[[int, Dict[str, Any], Optional[str]], None],
    ) -> None:
        if self.config.should_use_threading:
            threads = []
            for work_id in work_ids:
                threads.append(self._load_work(work_id, callback, threaded=True))
            for thread in threads:
                thread.join()
        else:
            for work_id in work_ids:
                self._load_work(work_id, callback)

    @AO3.threadable.threadable
    def _download_work(
        self,
        work_id: int,
        callback: Callable[[int, Dict[str, Any], Optional[str]], None],
    ) -> None:
        if work_id in self._downloaded and self._downloaded[work_id].is_file():
            LOG.info(f"Work id {work_id} is already downloaded, skipping.")
            callback(work_id, data={"path": self._downloaded[work_id]})
            return

        while True:
            wait_time = constants.INITIAL_WAIT_TIME_IN_SECONDS
            self._acquire_semaphore()
            try:
                work = self._works[work_id]
                filename = self._get_download_file_path(work)
                LOG.info(f"Downloading {work.id} - {work.title} to: {filename}")
                with open(filename, "wb") as f:
                    f.write(work.download(self.config.filetype))
                self._downloaded[work_id] = filename
                callback(work_id, data={"path": filename})
                self._release_semaphore()
                return
            except AO3.utils.HTTPError:
                LOG.warning(
                    f"Hit rate limit trying to download work {work_id}, "
                    f"trying again in {wait_time}s."
                )
                callback(
                    work_id,
                    data={"show_loading": True},
                    error_message=(f"Hit rate limit, trying again in {wait_time}s..."),
                )
                self._release_semaphore()
                time.sleep(wait_time)
                wait_time *= 2
            except Exception as e:
                LOG.error(f"Error downloading work id {work_id}: {e}. Skipping.")
                callback(work_id, error_message=str(e))
                self._release_semaphore()
                return

    def download_works(
        self,
        work_ids: Set[int],
        callback: Callable[[int, Dict[str, Any], Optional[str]], None],
    ) -> None:
        # Check download directory structure
        downloads_dir = self.config.downloads_dir / self.session.username
        downloads_dir.mkdir(parents=True, exist_ok=True)

        if self.config.should_use_threading:
            threads = []
            for work_id in work_ids:
                threads.append(self._download_work(work_id, callback, threaded=True))
            for thread in threads:
                thread.join()
        else:
            for work_id in work_ids:
                self._download_work(work_id, callback)

    def _get_download_file_path(self, work: Work) -> Path:
        return (
            self.config.downloads_dir
            / self.session.username
            / (f"{work.id}_{slugify(work.title)}.{self.config.filetype.lower()}")
        )

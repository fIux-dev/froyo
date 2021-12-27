import AO3
import enum
import logging
import os
import sys
import threading
import time

from pathlib import Path
from queue import Queue
from AO3 import GuestSession, Series, Session, User, Work
from dataclasses import dataclass
from slugify import slugify
from threading import Lock, Semaphore, Thread, Timer
from typing import Any, Callable, Dict, List, Optional, Set

from . import constants, utils
from .configuration import Configuration

LOG = logging.getLogger(__name__)


class Action(enum.Enum):
    _SENTINEL = 0
    LOAD = 1
    DOWNLOAD = 2
    REMOVE = 3


@dataclass
class WorkItem:
    work: Work
    download_path: Optional[Path] = None
    seconds_before_retry: int = constants.INITIAL_SECONDS_BEFORE_RETRY


GUICallback = Callable[[int, Optional[WorkItem], Optional[str]], None]


class Engine:
    base_dir: Path
    config: Configuration
    session: GuestSession

    _queue: Queue
    _items: Dict[int, WorkItem] = {}
    _items_lock: Lock
    _active_ids: Set[int] = set()
    _active_ids_lock: Lock

    _threads: List[Thread] = []
    _retries: Dict[int, Timer] = {}

    _before_work_load: Optional[GUICallback] = None
    _after_work_load: Optional[GUICallback] = None
    _before_work_download: Optional[GUICallback] = None
    _after_work_download: Optional[GUICallback] = None

    def __init__(self, cwd: str):
        self._queue = Queue()
        self._items_lock = Lock()
        self._active_ids_lock = Lock()

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

        n_workers = 1
        if self.config.should_use_threading and self.config.concurrency_limit > 1:
            n_workers = self.config.concurrency_limit
        self._init_worker_threads(n_workers)

    # Initialization functions
    def _init_worker_threads(self, n_workers: int):
        """Creates a thread pool of workers.

        These run separately from the main thread to parallelize sending
        web requests for loading, downloading, etc.
        """
        for _ in range(n_workers):
            thread = Thread(target=self._process_queue)
            thread.start()
            self._threads.append(thread)

    def set_before_work_load(self, f: GUICallback):
        """To be called by the GUI during its initialization.

        Sets a GUI function to be run before any work is loaded.
        """
        self._before_work_load = f

    def set_after_work_load(self, f: GUICallback):
        """To be called by the GUI during its initialization.

        Sets a GUI function to be run after any work is done loading.
        """
        self._after_work_load = f

    def set_before_work_download(self, f: GUICallback):
        """To be called by the GUI during its initialization.

        Sets a GUI function to be run before any work is downloaded.
        """
        self._before_work_download = f

    def set_after_work_download(self, f: GUICallback):
        """To be called by the GUI during its initialization.

        Sets a GUI function to be run before any work is down downloading.
        """
        self._after_work_download = f

    # Public API to be called from the GUI
    def login(self, username: str, password: str) -> int:
        """Attempts to login to AO3 with the specified credentials.

        TODO: make this non-blocking.
        """
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
        """Logs out from AO3 and use a guest session instead."""
        try:
            del self.session
            self.session = GuestSession()
            LOG.info("Logged out.")
            return 0
        except Exception:
            LOG.error("Error logging out.")
            return 1

    def get_settings(self) -> int:
        """Read current settings saved in the configuration file."""
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
        """Updates the current configuration object and write it to file."""
        self.config.username = username
        self.config.password = password
        self.config.downloads_dir = downloads_dir
        self.config.filetype = filetype
        self.config.should_use_threading = should_use_threading
        self.config.concurrency_limit = concurrency_limit
        self.config.should_rate_limit = should_rate_limit

        return self.config.write_to_file()

    def remove(self, work_id: int) -> bool:
        """Remove an ID from the active IDs set.

        This is usually called when the user removes a work through the GUI.
        """
        self._active_ids_lock.acquire()
        self._active_ids.remove(work_id)
        self._active_ids_lock.release()
        self._items_lock.acquire()
        if work_id in self._items:
            del self._items[work_id]
        self._items_lock.release()

    def remove_all(self) -> bool:
        """Remove all IDs from the active IDs set."""
        self._active_ids_lock.acquire()
        self._active_ids.clear()
        self._active_ids_lock.release()
        self._items_lock.acquire()
        self._items.clear()
        self._items_lock.release()

    def load_work(self, work_id: int) -> None:
        """Wrapper for enqueuing a load action."""
        self._enqueue_action(work_id, Action.LOAD)

    def load_works(self, work_ids: Set[int]) -> None:
        """Enqueue load actions for every ID in the active IDs set."""
        for work_id in work_ids:
            self._enqueue_action(work_id, Action.LOAD)

    def download_work(self, work_id: int) -> None:
        """Wrapper for enqueueing a download action."""
        self._enqueue_action(work_id, Action.DOWNLOAD)

    def download_all(self) -> None:
        """Enqueues download actions for all work IDs in the active set."""
        for work_id in self._active_ids:
            self._enqueue_action(work_id, Action.DOWNLOAD)

    def stop(self) -> None:
        """Shuts down the engine cleanly.

        Ensures all threads are properly terminated
        """
        LOG.info("Shutting down all worker threads...")
        self._queue.put((-1, Action._SENTINEL))
        self.remove_all()
        for thread in self._threads:
            thread.join()
        for _, threads in self._retries.items():
            for thread in threads:
                thread.cancel()
                thread.join()

    # These functions return a list of work IDs from the inputs.
    # TODO: make these asynchronous with retry. Right now if we get rate limited
    # during these stages it is not recoverable and there is no retry. The
    # functions will simply return no results.
    def urls_to_work_ids(self, urls: Set[str]) -> Set[int]:
        """Return work IDs for the URLs supplied."""
        ids = set()
        for url in urls:
            work_id = AO3.utils.workid_from_url(url)
            if work_id:
                ids.add(work_id)
            else:
                LOG.error(f"{url} was not a valid work URL, skipping.")
        return ids

    def series_urls_to_work_ids(self, urls: Set[str]) -> Set[int]:
        """Return work IDs for the series URL supplied.

        This will attempt to return every work ID for every series in the
        supplied list. Note that this can be rate limited, and there is no 
        retry logic yet.

        TODO: make this non-blocking
        """
        ids = set()
        for url in urls:
            series_id = utils.series_id_from_url(url)
            if series_id:
                LOG.info(f"Loading works from series {series_id}...")
                try:
                    series = Series(series_id)
                    ids.update(work.id for work in series.work_list)
                except Exception as e:
                    LOG.error(
                        f"Error getting work list for series URL {url}: {e}. Skipping."
                    )
            else:
                LOG.error(f"{url} was not a valid series URL, skipping.")
        return ids

    def usernames_to_work_ids(self, usernames: Set[str]) -> Set[int]:
        """Return work IDs for every username supplied.

        This will attempt to return works written by every user in the supplied
        list. Note that this can be rate limited, and there is no retry logic yet.

        TODO: make this non-blocking
        """
        ids = set()
        for username in usernames:
            LOG.info(f"Loading works by user {username}...")
            try:
                user = User(username)
                works = user.get_works(use_threading=self.config.should_use_threading)
                ids.update(work.id for work in works)
            except Exception as e:
                LOG.error(f"Error getting works by user: {username}: {e}. Skipping.")
        return ids

    def usernames_to_bookmark_ids(self, usernames: Set[str]) -> Set[int]:
        """Return work IDs for bookmarks of every username supplied.

        This will attempt to return bookmarks of every user in the supplied
        list. Note that this can be rate limited, and there is no retry logic yet.

        TODO: make this non-blocking
        """
        ids = set()
        for username in usernames:
            LOG.info(f"Loading bookmarks from user {username}...")
            try:
                user = User(username)
                bookmarks = user.get_bookmarks(
                    use_threading=self.config.should_use_threading
                )
                ids.update(work.id for work in bookmarks)
            except Exception as e:
                LOG.error(
                    f"Error getting bookmarks for user: {username}: {e}. Skipping."
                )
        return ids

    def get_self_bookmarks(self) -> Set[int]:
        """Return work IDs for current session user.

        This will attempt to return every bookmark by the current user.
        Note that this can be rate limited, and there is no retry logic yet.

        TODO: make this non-blocking
        """
        ids = set()
        try:
            LOG.info("Loading bookmarked works...")
            # TODO: send PR to AO3 API to make this work for series bookmarks
            bookmarks = self.session.get_bookmarks(
                use_threading=self.config.should_use_threading
            )
            ids.update(work.id for work in bookmarks)
        except Exception as e:
            LOG.error(
                f"Error getting bookmarks for user: {self.session.username}: {e}. Skipping."
            )
        return ids

    # Threading helper functions
    def _enqueue_action(self, work_id: int, action: Action):
        """Enqueues a value on the worker queue if the ID is active.

        This is locking because multiple threads can be accessing the active
        ID set.
        """
        self._active_ids_lock.acquire()
        self._active_ids.add(work_id)
        self._active_ids_lock.release()
        self._queue.put((work_id, action))

    def _is_id_active(self, work_id):
        """Locking read of the active ID set.
    
        If an ID is not active, it may have been deleted by the user through
        the GUI. In that case, we no longer care about existing queued actions
        for this ID, so we can discard those tasks in the worker threads.
        """
        self._active_ids_lock.acquire()
        is_active = work_id in self._active_ids
        self._active_ids_lock.release()
        return is_active

    def _update_item(self, work_id: int, item: WorkItem):
        """Updates the item cache with the provided value.

        This requries acquiring the lock first in order to prevent corruption
        of the active ID set, since many threads can be accessing it at the same
        time.
        """
        self._items_lock.acquire()
        self._items[work_id] = item
        self._items_lock.release()

    def _cancel_retries(self, work_id: int, action: Action):
        """Cancel all current threads attempting to retry this (work_id, action).

        Usually called when the action succeeds in another thread.
        """
        if (work_id, action) not in self._retries:
            return

        for thread in self._retries[(work_id, action)]:
            if thread is threading.current_thread():
                continue
            else:
                thread.cancel()
                thread.join()

    def _retry(self, seconds_before_retry: int, work_id: int, action: Action):
        """Spawn a new thread to enqueue the action again after some time.
        """
        retry = Timer(seconds_before_retry, self._queue.put, args=((work_id, action),))
        retry.start()

        key = (work_id, action)
        if key in self._retries:
            self._retries[key].append(retry)
        else:
            self._retries[key] = [retry]

    def _process_queue(self):
        """Function run by worker threads.

        Will attempt to continually process the queue while there are pending
        items and perform those requests.
        """
        while True:
            work_id, action = self._queue.get(block=True)
            if action == Action._SENTINEL:
                # Exit
                self._queue.put((-1, Action._SENTINEL))
                return
            elif action == Action.LOAD:
                self._load_work(work_id)
            elif action == Action.DOWNLOAD:
                self._download_work(work_id)

    def _reload_work_with_current_session(self, work: Work) -> None:
        """Function to be called from a worker thread.

        This will attempt to reload the work using the current session.
        """
        try:
            work.set_session(self.session)
            # TODO: determine whether load_chapters=False is useful here.
            work.reload(load_chapters=False)
            LOG.info(f"Loaded work id {work.id}.")
        except AttributeError:
            # This is a hack due to how the AO3 API works right now.
            LOG.warning(f"Work {work.id} is only accessible to logged-in users.")
            raise AO3.utils.AuthError("Work is only accessible to logged-in users.")

    def _load_work(self, work_id: int,) -> None:
        """Function to be called from a worker thread.

        This will return the cached value if the work was determined to be
        already loaded, otherwise it will attempt to load work metadata, 
        retrying if a rate limit error occurs.
        """
        if not self._is_id_active(work_id):
            return

        self._before_work_load(work_id)
        work_item = self._items.get(work_id, WorkItem(work=Work(work_id, load=False)))
        if work_item.work.loaded:
            LOG.info(f"Work id {work_id} was already loaded, skipping.")
            self._after_work_load(work_id, work_item)
            return

        try:
            self._reload_work_with_current_session(work_item.work)
            self._after_work_load(work_id, work_item)
            self._update_item(work_id, work_item)
            self._cancel_retries(work_id, Action.LOAD)
        except AO3.utils.HTTPError:
            LOG.warning(
                f"Hit rate limit trying to load work {work_id}, "
                f"trying again in {work_item.seconds_before_retry}s."
            )
            # TODO: make this a decorator
            self._retry(work_item.seconds_before_retry, work_item.work.id, Action.LOAD)
            self._after_work_load(
                work_id,
                None,
                error=(
                    f"Hit rate limit, trying again in {work_item.seconds_before_retry}s..."
                ),
            )
            work_item.seconds_before_retry *= 2
            self._update_item(work_id, work_item)
        except Exception as e:
            LOG.error(f"Error loading work id {work_id}: {e}")
            self._after_work_load(work_id, None, error=str(e))

    def _download_work(self, work_id: int,) -> None:
        """Function to be called from a worker thread.

        Before downloading, the work must also be loaded if it is not already.

        This will return the cached value if the work was determined to be
        already downloaded, otherwise it will attempt to download, retrying
        if a rate limit error occurs.
        """
        if not self._is_id_active(work_id):
            return

        self._before_work_download(work_id)
        work_item = self._items.get(work_id, WorkItem(work=Work(work_id, load=False)))
        if work_item.download_path and work_item.download_path.is_file():
            LOG.info(f"Work id {work_id} was already downloaded, skipping.")
            self._after_work_download(work_id, work_item)
            return

        try:
            if not work_item.work.loaded:
                self._before_work_load(work_id)
                self._reload_work_with_current_session(work_item.work)
                self._after_work_load(work_id, work_item)
            download_path = self._get_download_file_path(work_item.work)
            LOG.info(
                f"Downloading {work_item.work.id} - {work_item.work.title} to: {download_path}"
            )
            work_item.work.download_to_file(download_path, self.config.filetype)
            work_item.download_path = download_path
            self._after_work_download(work_id, work_item)
            self._update_item(work_id, work_item)
            self._cancel_retries(work_id, Action.DOWNLOAD)
        except AO3.utils.HTTPError:
            LOG.warning(
                f"Hit rate limit trying to download work {work_id}, "
                f"trying again in {work_item.seconds_before_retry}s."
            )
            # TODO: make this a decorator
            self._retry(
                work_item.seconds_before_retry, work_item.work.id, Action.DOWNLOAD
            )
            self._after_work_download(
                work_id,
                None,
                error=(
                    f"Hit rate limit, trying again in {work_item.seconds_before_retry}s..."
                ),
            )
            work_item.seconds_before_retry *= 2
            self._update_item(work_id, work_item)
        except Exception as e:
            LOG.error(f"Error downloading work id {work_id}: {e}")
            self._after_work_download(work_id, None, error=str(e))

    # Utility functions
    def _get_download_file_path(self, work: Work) -> Path:
        """Utility function for getting a path to save a work.

        This will sanitize the filename into something that is safer for use
        with cross-platform filesystems. The file will be saved in the download
        directory specified in the configuration, and optionally in a folder
        with the logged-in user's username.
        """
        return (
            self.config.downloads_dir
            / self.session.username
            / (f"{work.id}_{slugify(work.title)}.{self.config.filetype.lower()}")
        )

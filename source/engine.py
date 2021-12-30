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
from threading import Lock, Thread, Timer
from typing import Any, Callable, Dict, Hashable, List, Optional, Set, Tuple, Union

from . import ao3_extensions, constants, utils
from .ao3_extensions import Results, ResultsPage
from .configuration import Configuration

LOG = logging.getLogger(__name__)


class Action(enum.Enum):
    _SENTINEL = 0
    LOAD_WORK = 1
    DOWNLOAD_WORK = 2
    LOAD_SERIES = 3
    LOAD_USER_WORKS = 4
    LOAD_USER_BOOKMARKS = 5
    LOAD_RESULTS_LIST = 6
    LOAD_RESULTS_PAGE = 7
    LOGIN = 8


class Status(enum.Enum):
    OK = 0
    ERROR = 1
    RETRY = 2


@dataclass
class WorkItem:
    work: Work
    download_path: Optional[Path] = None


GUICallback = Callable[..., None]
Args = List[Any]
Kwargs = Dict[str, Any]


class Engine:
    base_dir: Path
    config: Configuration
    session: GuestSession

    _queue: Queue
    _items: Dict[int, WorkItem] = {}
    _active_ids: Set[int] = set()
    _threads: List[Thread] = []
    _retries: Dict[Hashable, List[Timer]] = {}

    _time_before_retry: int = constants.INITIAL_SECONDS_BEFORE_RETRY

    _items_lock: Lock
    _active_ids_lock: Lock
    _retry_lock: Lock

    _action_callbacks: Dict[Action, Tuple[Optional[GUICallback], Optional[GUICallback]]]
    _enqueue_callbacks: Dict[
        Action, Tuple[Optional[GUICallback], Optional[GUICallback]]
    ]

    def __init__(self, base_directory: Path):
        self._queue = Queue()
        self._action_callbacks = {action: (None, None) for action in Action}
        self._enqueue_callbacks = {action: (None, None) for action in Action}

        self._items_lock = Lock()
        self._active_ids_lock = Lock()
        self._retry_lock = Lock()

        self.base_dir = base_directory
        LOG.info(f"Current working directory: {self.base_dir}")

        # Validate data directory structure
        data_dir = self.base_dir / constants.DATA_DIR
        data_dir.mkdir(parents=True, exist_ok=True)

        # Create default configuration, but load settings from file if it exists
        self.session = GuestSession()
        self.config = Configuration(self.base_dir / constants.CONFIGURATION_FILE)

        if self.config.should_rate_limit:
            AO3.utils.limit_requests()

        # Initialize worker threads
        n_workers = 1
        if self.config.should_use_threading and self.config.concurrency_limit > 1:
            n_workers = self.config.concurrency_limit
        self._init_worker_threads(n_workers)

    # Initialization functions
    def _init_worker_threads(self, n_workers: int) -> None:
        """Creates a thread pool of workers.

        These run separately from the main thread to parallelize sending
        web requests for loading, downloading, etc.
        """
        for _ in range(n_workers):
            thread = Thread(target=self._process_queue)
            thread.start()
            self._threads.append(thread)

    # Functions for interacting with GUI callbacks
    def set_action_callbacks(
        self,
        callbacks: Dict[Action, Tuple[Optional[GUICallback], Optional[GUICallback]]],
    ) -> None:
        """Sets the callbacks (before, after) for each action."""
        self._action_callbacks.update(callbacks)

    def set_enqueue_callbacks(
        self,
        callbacks: Dict[Action, Tuple[Optional[GUICallback], Optional[GUICallback]]],
    ) -> None:
        """Sets the callbacks to be run when enqueuing action."""
        self._enqueue_callbacks.update(callbacks)

    def _run_before_enqueue(
        self, action: Action, args: Args = [], kwargs: Kwargs = {}
    ) -> None:
        """If a callback is registered to be run before enqueueing the action, 
        run it."""
        before_enqueue = self._enqueue_callbacks[action][0]
        if before_enqueue:
            before_enqueue(*args, **kwargs)

    def _run_after_enqueue(
        self, action: Action, args: Args = [], kwargs: Kwargs = {}
    ) -> None:
        """If a callback is registered to be run after enqueueing the action, 
        run it."""
        after_enqueue = self._enqueue_callbacks[action][1]
        if after_enqueue:
            after_enqueue(*args, **kwargs)

    def _run_before_action(
        self, action: Action, args: Args = [], kwargs: Kwargs = {}
    ) -> None:
        """If a callback is registered to be run before the action, run it."""
        before_action = self._action_callbacks[action][0]
        if before_action:
            before_action(*args, **kwargs)

    def _run_after_action(
        self, action: Action, args: Args = [], kwargs: Kwargs = {}
    ) -> None:
        """If a callback is registered to be run after the action, run it."""
        after_action = self._action_callbacks[action][1]
        if after_action:
            after_action(*args, **kwargs)

    # Public API to be called from the GUI
    def login(self, username: str, password: str) -> None:
        """Attempts to login to AO3 with the specified credentials."""
        self._enqueue_action((username, password), Action.LOGIN)

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
        except Exception as e:
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

    def remove(self, work_id: int) -> None:
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
        for action in Action:
            self._cancel_retries(work_id, action)

    def remove_all(self) -> None:
        """Remove all IDs from the active IDs set.

        The removal functions are CPU bound so it's okay to be non-async here.
        """
        self._active_ids_lock.acquire()
        self._active_ids.clear()
        self._active_ids_lock.release()
        self._items_lock.acquire()
        self._items.clear()
        self._items_lock.release()
        self._cancel_all_retries()

    def download_work(self, work_id: int) -> None:
        """Wrapper for enqueueing a download action."""
        self._verify_download_directory_exists()
        self._enqueue_work_action(work_id, Action.DOWNLOAD_WORK)

    def download_all(self) -> None:
        """Enqueues download actions for all work IDs in the active set."""
        self._verify_download_directory_exists()
        for work_id in self._active_ids:
            self._enqueue_work_action(work_id, Action.DOWNLOAD_WORK)

    def stop(self) -> None:
        """Shuts down the engine cleanly.

        Ensures all threads are properly terminated
        """
        LOG.info("Shutting down engine, please wait...")
        self._queue.put((-1, Action._SENTINEL))
        self.remove_all()
        LOG.info("Shutting down worker threads.")
        for thread in self._threads:
            thread.join()
        LOG.info("Shut down worker threads.")
        LOG.info("Shuting down retry threads...")
        self._cancel_all_retries()
        LOG.info("Shut down retry threads.")

    def load_works_from_work_urls(self, urls: Set[str]) -> None:
        """Load works from the URLs supplied."""
        for url in urls:
            work_id = AO3.utils.workid_from_url(url)
            if work_id:
                self._enqueue_work_action(work_id, Action.LOAD_WORK)
            else:
                LOG.error(f"{url} was not a valid work URL, skipping.")

    def load_works_from_series_urls(self, urls: Set[str]) -> None:
        """Load works from the series URLs supplied.

        This will attempt to load every work ID for every series in the
        supplied list.
        """
        for url in urls:
            series_id = utils.series_id_from_url(url)
            if series_id:
                LOG.info(f"Loading works from series {series_id}...")
                self._enqueue_action(series_id, Action.LOAD_SERIES)
            else:
                LOG.error(f"{url} was not a valid series URL, skipping.")

    def load_works_by_usernames(self, usernames: Set[str]) -> None:
        """Load works by every username supplied.

        This will attempt to load works written by every user in the supplied
        list.
        """
        for username in usernames:
            self._enqueue_action(username, Action.LOAD_USER_WORKS)

    def load_bookmarks_by_usernames(self, usernames: Set[str]) -> None:
        """Load bookmarks by every username supplied.

        This will attempt to load bookmarks of every user in the supplied
        list.
        """
        for username in usernames:
            self._enqueue_action(username, Action.LOAD_USER_BOOKMARKS)

    def load_works_from_generic_url(
        self, url: str, page_start: int, page_end: int
    ) -> None:
        """Load works from the URLs supplied."""
        ao3_url = ao3_extensions.get_ao3_url(url)
        if ao3_url is not None:
            if page_start == page_end:
                self._enqueue_action((ao3_url, page_start), Action.LOAD_RESULTS_PAGE)
            else:
                self._enqueue_action(
                    (ao3_url, page_start, page_end), Action.LOAD_RESULTS_LIST
                )
        else:
            LOG.error(f"{url} was not a valid AO3 URL, skipping.")

    # Threading helper functions
    def _enqueue_work_action(self, work_id: int, action: Action) -> None:
        """Enqueues an (id, action) entry on the worker queue.

        This should only be used for works since it adds to the active ID set.
        """
        self._active_ids_lock.acquire()
        self._active_ids.add(work_id)
        self._active_ids_lock.release()
        self._enqueue_action(work_id, action, run_callbacks=True)

    def _enqueue_action(
        self, identifier: Hashable, action: Action, run_callbacks=False
    ) -> None:
        """Enqueues an (id, action) entry on the worker queue.
        """
        if not run_callbacks:
            self._queue.put((identifier, action))
            return

        self._run_before_enqueue(action, args=[identifier])
        self._queue.put((identifier, action))
        self._run_after_enqueue(action, args=[identifier])

    def _is_work_id_active(self, work_id: int, action: Action) -> bool:
        """Locking read of the active work ID set.
    
        If an ID is not active, it may have been deleted by the user through
        the GUI. In that case, we no longer care about existing queued actions
        for this ID, so we can discard those tasks in the worker threads.

        This should only work for works. For things like series, users, this
        should always return true.

        TODO: track series and users as separate identifier sets
        """
        if action not in {Action.LOAD_WORK, Action.DOWNLOAD_WORK}:
            return True

        self._active_ids_lock.acquire()
        is_active = work_id in self._active_ids
        self._active_ids_lock.release()
        return is_active

    def _get_work_item(self, work_id: int) -> Optional[WorkItem]:
        """Updates the item cache with the provided value.

        This requries acquiring the lock first in order to prevent corruption
        of the active ID set, since many threads can be accessing it at the same
        time.
        """
        self._items_lock.acquire()
        work_item = self._items.get(work_id, None)
        self._items_lock.release()
        return work_item

    def _set_work_item(self, work_id: int, item: WorkItem) -> None:
        """Updates the item cache with the provided value.

        This requries acquiring the lock first in order to prevent corruption
        of the active ID set, since many threads can be accessing it at the same
        time.
        """
        self._items_lock.acquire()
        self._items[work_id] = item
        self._items_lock.release()

    def _cancel_retries(self, identifier: Hashable, action: Action) -> None:
        """Cancel all current threads attempting to retry this (identifier, action).

        Usually called when the action succeeds in another thread.
        """
        key = (identifier, action)
        self._retry_lock.acquire()
        if key not in self._retries:
            self._retry_lock.release()
            return

        for thread in self._retries[key]:
            thread.cancel()
            thread.join()

        del self._retries[(identifier, action)]
        self._retry_lock.release()

    def _cancel_all_retries(self) -> None:
        """Cancel all retries."""
        self._retry_lock.acquire()
        for identifier in list(self._retries):
            threads = self._retries.pop(identifier)
            for thread in threads:
                thread.cancel()
                thread.join()
        self._retry_lock.release()

    def _get_seconds_before_retry(self, identifier: Hashable, action: Action) -> int:
        """Get the time in seconds to wait before retrying the action for the ID.

        The wait time increases exponentially, doubling based on how many times
        we have attempted to retry.
        """
        self._retry_lock.acquire()
        n_retries = len(self._retries.get((identifier, action), []))
        self._retry_lock.release()
        retry_time = constants.INITIAL_SECONDS_BEFORE_RETRY * (1 << n_retries)
        return retry_time

    def _retry(self, identifier: Hashable, action: Action, wait_time: int) -> None:
        """Spawn a new thread to enqueue the action again after some time.
        """
        LOG.info(
            f"Retry {action.name} for identifier {identifier} after {wait_time}s..."
        )
        self._retry_lock.acquire()

        retry = Timer(wait_time, self._enqueue_action, args=(identifier, action))
        retry.start()

        key = (identifier, action)
        if key in self._retries:
            self._retries[key].append(retry)
        else:
            self._retries[key] = [retry]

        self._retry_lock.release()

    def _process_queue(self) -> None:
        """Function run by worker threads.

        Will attempt to continually process the queue while there are pending
        items and perform those requests.
        """
        while True:
            identifier, action = self._queue.get()
            if action == Action._SENTINEL:
                # Exit condition
                self._queue.put((-1, Action._SENTINEL))
                return

            if not self._is_work_id_active(identifier, action):
                # If the work ID is not in the active set, this usually indicates
                # that the user deleted the work through the UI. This means
                # there is no longer a need to process this request.
                continue

            args = [identifier]
            self._run_before_action(action, args=args)

            status = Status.ERROR
            kwargs = {}
            if action == Action.LOAD_WORK:
                status, kwargs = self._load_work(identifier)
            elif action == Action.DOWNLOAD_WORK:
                status, kwargs = self._download_work(identifier)
            elif action == Action.LOAD_SERIES:
                status, kwargs = self._load_works_from_series(identifier)
            elif action == Action.LOAD_USER_WORKS:
                status, kwargs = self._load_works_from_user(identifier)
            elif action == Action.LOAD_USER_BOOKMARKS:
                status, kwargs = self._load_bookmarks_from_user(identifier)
            elif action == Action.LOAD_RESULTS_LIST:
                url, page_start, page_end = identifier
                status, kwargs = self._load_pages_from_results_list(
                    url, page_start, page_end
                )
            elif action == Action.LOAD_RESULTS_PAGE:
                url, page = identifier
                status, kwargs = self._load_works_from_results_page(url, page)
            elif action == Action.LOGIN:
                username, password = identifier
                status, kwargs = self._login(username, password)

            if not self._is_work_id_active(identifier, action):
                # Again, work ID may have been removed since the processing was
                # done. If so, there is no need to run retry or the callback.
                continue

            if status == Status.RETRY:
                wait_time = self._get_seconds_before_retry(identifier, action)
                self._retry(identifier, action, wait_time)
                kwargs["error"] = f"Hit rate limit, trying again in {wait_time}s..."
            elif status == Status.OK:
                self._cancel_retries(identifier, action)

            args.append(status)
            self._run_after_action(action, args=args, kwargs=kwargs)

    def _reload_work_with_current_session(self, work: Work) -> None:
        """Function to be called from a worker thread.

        This will attempt to reload the work using the current session.
        """
        try:
            work.set_session(self.session)
            # TODO: determine whether load_chapters=False is useful here.
            work.reload(load_chapters=False)
            LOG.info(f"Loaded work id {work.id}.")
        except AttributeError as e:
            # This is a hack due to how the AO3 API works right now.
            if not self.session.is_authed:
                LOG.warning(f"Work {work.id} is only accessible to logged-in users.")
                raise AO3.utils.AuthError("Work is only accessible to logged-in users.")
            else:
                raise e

    def _login(self, username: str, password: str) -> Tuple[Status, Kwargs]:
        """Function to be called from a worker thread.

        This will try to login with the specified credentials.
        """
        self.session = GuestSession()
        try:
            self.session = Session(username, password)
            self.session.refresh_auth_token()
            LOG.info(f"Authenticated as user: {self.session.username}")
            return (Status.OK, {"user": self.session.user})
        except AO3.utils.HTTPError as e:
            LOG.error(f"HTTP error: {e}. Not logged in.")
            return (Status.ERROR, {"error": "You are being rate limited"})
        except AO3.utils.LoginError:
            LOG.error("Invalid username or password.")
            return (Status.ERROR, {"error": "Invalid username or password"})
        except Exception as e:
            LOG.error(f"Error logging in: {e}")
            return (Status.ERROR, {"error": str(e)})

    def _load_work(self, work_id: int) -> Tuple[Status, Kwargs]:
        """Function to be called from a worker thread.

        This will return the cached value if the work was determined to be
        already loaded, otherwise it will attempt to load work metadata, 
        retrying if a rate limit error occurs.
        """
        work_item = self._get_work_item(work_id) or WorkItem(
            work=Work(work_id, load=False)
        )

        if work_item.work.loaded:
            LOG.info(f"Work id {work_id} was already loaded, skipping.")
            return (Status.OK, {"work_item": work_item})

        try:
            self._reload_work_with_current_session(work_item.work)
            self._set_work_item(work_id, work_item)
            return (Status.OK, {"work_item": work_item})
        except AO3.utils.HTTPError:
            LOG.warning(
                f"Hit rate limit trying to load work {work_id}. Attempting to retry..."
            )
            return (Status.RETRY, {})
        except Exception as e:
            LOG.error(f"Error loading work id {work_id}: {e}")
            return (Status.ERROR, {"error": str(e)})

    def _download_work(self, work_id: int) -> Tuple[Status, Kwargs]:
        """Function to be called from a worker thread.

        Before downloading, the work must also be loaded if it is not already.

        This will return the cached value if the work was determined to be
        already downloaded, otherwise it will attempt to download, retrying
        if a rate limit error occurs.
        """
        work_item = self._get_work_item(work_id) or WorkItem(
            work=Work(work_id, load=False)
        )

        if work_item.download_path and work_item.download_path.is_file():
            LOG.info(f"Work id {work_id} was already downloaded, skipping.")
            return (Status.OK, {"work_item": work_item})

        try:
            if not work_item.work.loaded:
                # Make sure we're loaded before we download
                self._run_before_action(Action.LOAD_WORK, args=[work_id])
                status, kwargs = self._load_work(work_id)
                self._run_after_action(
                    Action.LOAD_WORK, args=[work_id, status], kwargs=kwargs
                )
                if status != Status.OK:
                    return (status, kwargs)
                self._cancel_retries(work_id, Action.LOAD_WORK)

            download_path = self._get_download_file_path(work_item.work)
            LOG.info(
                f"Downloading {work_item.work.id} - {work_item.work.title} to: {download_path}"
            )
            # Use this instead of work.download_to_file to prevent zero-byte files.
            content = work_item.work.download(self.config.filetype)
            if not content:
                return (Status.ERROR, {"error": "Downloaded 0 bytes"})
            with open(download_path, "wb") as file:
                file.write(content)
            work_item.download_path = download_path
            self._set_work_item(work_id, work_item)
            return (Status.OK, {"work_item": work_item})
        except (AttributeError, AO3.utils.HTTPError):
            # This is a hack due to how the AO3 API works right now. Since the
            # work must be loaded before download, AttributeError due to the
            # work not being accessible should be propagated from the load.
            # work_item.work.download can throw since the soup object can be
            # None when we are being rate limited.
            LOG.warning(
                f"Hit rate limit trying to download work {work_id}. Attempting to retry..."
            )
            return (Status.RETRY, {})
        except Exception as e:
            LOG.error(f"Error downloading work id {work_id}: {e}")
            return (Status.ERROR, {"error": str(e)})

    def _load_works_from_series(self, series_id: int) -> Tuple[Status, Kwargs]:
        """Function to be called from a worker thread.

        This will enqueue all works in the series worklist to be loaded.

        TODO: cache these values.
        TODO: make series loads cancellable.
        TODO: look into pausing and resuming if the series list is really long.
        """
        try:
            series = Series(series_id)
            for work in series.work_list:
                self._enqueue_work_action(work.id, Action.LOAD_WORK)
            return (Status.OK, {"series": series})
        except AO3.utils.HTTPError:
            LOG.warning(
                f"Hit rate limit trying to load series {series_id}. Attempting to retry..."
            )
            return (Status.RETRY, {})
        except Exception as e:
            LOG.error(f"Error loading series id {series_id}: {e}")
            return (Status.ERROR, {"error": str(e)})

    def _load_works_from_user(self, username: str) -> Tuple[Status, Kwargs]:
        """Function to be called from a worker thread.

        This will enqueue all works by the specified username.

        TODO: cache these values.
        TODO: make user loads cancellable.
        TODO: look into pausing and resuming if the work list is really long.
        """
        try:
            # TODO: send PR to AO3 API to enable loading only works or bookmarks
            if not utils.does_user_exist(username, self.session.session):
                return (Status.ERROR, {"error": "User does not exist"})

            user = User(username)
            works = user.get_works(use_threading=self.config.should_use_threading)
            for work in works:
                self._enqueue_work_action(work.id, Action.LOAD_WORK)
            return (Status.OK, {"user": user})
        except (AttributeError, AO3.utils.HTTPError):
            # This is a hack due to how the AO3 API works right now.
            LOG.warning(
                f"Hit rate limit trying to load works from user {username}. "
                f"Attempting to retry..."
            )
            return (Status.RETRY, {})
        except Exception as e:
            LOG.error(f"Error loading works from user {username}: {e}")
            return (Status.ERROR, {"error": str(e)})

    def _load_bookmarks_from_user(self, username: str) -> Tuple[Status, Kwargs]:
        """Function to be called from a worker thread.

        This will enqueue all bookmarks by the specified username.

        TODO: cache these values.
        TODO: make user loads cancellable.
        TODO: look into pausing and resuming if the work list is really long.
        """
        try:
            bookmarks = []
            kwargs = {}
            if username == self.session.username and isinstance(
                self.session, AO3.Session
            ):
                bookmarks = self.session.get_bookmarks(
                    use_threading=self.config.should_use_threading
                )
            else:
                if not utils.does_user_exist(username, self.session.session):
                    return (Status.ERROR, {"error": "User does not exist"})

                user = User(username)
                bookmarks = user.get_bookmarks(
                    use_threading=self.config.should_use_threading
                )
                kwargs = {"user": user}
            for work in bookmarks:
                self._enqueue_work_action(work.id, Action.LOAD_WORK)
            return (Status.OK, kwargs)
        except (AttributeError, AO3.utils.HTTPError):
            # This is a hack due to how the AO3 API works right now.
            LOG.warning(
                f"Hit rate limit trying to load bookmarks from user {username}. "
                f"Attempting to retry..."
            )
            return (Status.RETRY, {})
        except Exception as e:
            LOG.error(f"Error loading bookmarks from user {username}: {e}")
            return (Status.ERROR, {"error": str(e)})

    def _load_pages_from_results_list(
        self, url: str, page_start: int, page_end: int
    ) -> Tuple[Status, Kwargs]:
        """Function to be called from a worker thread.

        This will enqueue all pages in the range to be loaded so that the works
        on those pages can be loaded.
        """
        try:
            results = Results(url, page_start, page_end, self.session.session)
            results.update()
            for page in range(
                max(1, results.page_start), min(results.pages, results.page_end) + 1
            ):
                self._enqueue_action((url, page), Action.LOAD_RESULTS_PAGE)
            return (Status.OK, {"results": results})
        except AO3.utils.HTTPError:
            LOG.warning(
                f"Hit rate limit trying to load url `{url}`. " f"Attempting to retry..."
            )
            return (Status.RETRY, {})
        except Exception as e:
            LOG.error(f"Error loading results list for url `{url}`: {e}")
            return (Status.ERROR, {"error": str(e)})

    def _load_works_from_results_page(
        self, url: str, page: int
    ) -> Tuple[Status, Kwargs]:
        """Function to be called from a worker thread.

        This will enqueue all works on the page to be loaded.
        """
        try:
            results_page = ResultsPage(url, page, self.session.session)
            results_page.update()
            for work_id in results_page.work_ids:
                self._enqueue_work_action(work_id, Action.LOAD_WORK)
            return (Status.OK, {"results_page": results_page})
        except AO3.utils.HTTPError:
            LOG.warning(
                f"Hit rate limit trying to load page {page} of url `{url}`. "
                f"Attempting to retry..."
            )
            return (Status.RETRY, {})
        except Exception as e:
            LOG.error(f"Error loading results page {page} for url `{url}`: {e}")
            return (Status.ERROR, {"error": str(e)})

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

    def _verify_download_directory_exists(self) -> None:
        """Verify the download directory exists, and create it if it doesn't."""
        downloads_dir = self.config.downloads_dir / self.session.username
        downloads_dir.mkdir(parents=True, exist_ok=True)

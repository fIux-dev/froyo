import dearpygui.dearpygui as dpg
import logging

from AO3 import Work
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

from . import constants, utils
from .engine import Engine, WorkItem
from .configuration import Configuration

LOG = logging.getLogger(__name__)


class GUI:
    engine: Optional[Engine] = None

    _work_ids: Set[int]
    _downloaded: Set[int]

    def __init__(self, engine: Engine = None):
        self.engine = engine
        self._work_ids = set()
        self._downloaded = set()

        if engine:
            self.engine.set_before_work_load(self._show_work_item_loading)
            self.engine.set_after_work_load(self._update_work_item_after_load)
            self.engine.set_before_work_download(self._show_work_item_downloading)
            self.engine.set_after_work_download(self._update_work_item_after_download)

    def _set_status_text_conditionally(
        self,
        tag: str,
        result: int,
        success_text: str,
        error_text: str,
        success_color: Tuple[int, int, int] = (0, 255, 0),
        error_color: Tuple[int, int, int] = (255, 0, 0),
    ):
        """Utility function for setting a text item.

        If result is 0, set the text to `success_text` and the color to
        `success_color`. Otherwise, set the text to `error_text` and the color 
        to `error_color`.
        """
        color = error_color
        text = error_text
        if result == 0:
            color = success_color
            text = success_text
        dpg.set_value(tag, text)
        dpg.configure_item(tag, color=color, show=True)

    def _login(self, sender=None, data=None) -> None:
        """Callback for clicking the login button.

        Calls the login function on the engine and displays the status.
        """
        dpg.configure_item("login_status_text", color=(255, 255, 0), show=True)
        dpg.set_value("login_status_text", "Logging in...")

        username = dpg.get_value("username_input")
        password = dpg.get_value("password_input")

        result = self.engine.login(username, password)
        self._set_status_text_conditionally(
            "login_status_text",
            result,
            f"Logged in as: {self.engine.session.username}",
            "Login error",
        )

    def _logout(self, sender=None, data=None) -> None:
        """Callback for clicking the logout button.

        Calls the logout function on the engine and displays the status.
        """
        dpg.configure_item("login_status_text", show=False)

        dpg.set_value("username_input", "")
        dpg.set_value("password_input", "")

        result = self.engine.logout()
        self._set_status_text_conditionally(
            "login_status_text", result, "Logged out", "Logout error"
        )
        dpg.set_value("remember_me_checkbox", False)

    def _set_downloads_dir(self, sender=None, data=None) -> None:
        """Callback for exiting the downloads directory selection file dialog.

        This sets the text input for the download directory to the selected
        directory from the file dialog.
        """
        dpg.set_value("downloads_dir_input", data["file_path_name"])

    def _show_downloads_dir_dialog(self, sender=None, data=None) -> None:
        """Callback for browsing for download directory in settings.

        Creates a new dialog allowing the user to select a directory.
        """
        if dpg.does_item_exist("downloads_dir_dialog"):
            dpg.delete_item("downloads_dir_dialog")

        dpg.add_file_dialog(
            tag="downloads_dir_dialog",
            directory_selector=True,
            default_path=dpg.get_value("downloads_dir_input"),
            callback=self._set_downloads_dir,
        )

    def _save_settings(self, sender=None, data=None) -> None:
        """Callback for clicking the save settings button.

        Writes the configuration to file.
        """
        dpg.configure_item("settings_status_text", show=False)

        username = ""
        password = ""
        if dpg.get_value("remember_me_checkbox"):
            username = dpg.get_value("username_input")
            password = dpg.get_value("password_input")
        downloads_dir = Path(dpg.get_value("downloads_dir_input"))
        filetype = dpg.get_value("filetype_combo")
        should_use_threading = dpg.get_value("use_threading_checkbox")
        concurrency_limit = dpg.get_value("concurrency_limit_input")
        should_rate_limit = dpg.get_value("rate_limit_checkbox")
        result = self.engine.update_settings(
            username=username,
            password=password,
            downloads_dir=downloads_dir,
            filetype=filetype,
            should_use_threading=should_use_threading,
            concurrency_limit=concurrency_limit,
            should_rate_limit=should_rate_limit,
        )

        self._set_status_text_conditionally(
            "settings_status_text",
            result,
            "Saved! Restart for engine changes.",
            "Save error",
        )

    def _reset_settings(self, sender=None, data=None) -> None:
        """Callback for clicking the reset settings button.

        Re-reads the existing configuration file.
        """
        dpg.configure_item("settings_status_text", show=False)
        result = self.engine.get_settings()

        if result == 0:
            dpg.set_value("username_input", self.engine.config.username)
            dpg.set_value("password_input", self.engine.config.password)
            dpg.set_value(
                "remember_me_checkbox",
                any((self.engine.config.username, self.engine.config.password)),
            )
            dpg.set_value("downloads_dir_input", str(self.engine.config.downloads_dir))
            dpg.set_value("filetype_combo", self.engine.config.filetype)
            dpg.set_value("rate_limit_checkbox", self.engine.config.should_rate_limit)
            dpg.set_value(
                "use_threading_checkbox", self.engine.config.should_use_threading
            )
            dpg.set_value(
                "concurrency_limit_input", self.engine.config.concurrency_limit
            )

        self._set_status_text_conditionally(
            "settings_status_text",
            result,
            "Loaded saved settings!",
            "Error loading settings",
        )

    def _open_file(self, sender=None, data=None, user_data=None):
        """Callback for clicking the open button on a work.

        Tries to open the destination of the downloaded file with the system
        default applications.
        """
        # TODO: add a message if file could not be opened
        work_id = user_data["work_id"]
        try:
            utils.open_file(user_data["path"])
        except FileNotFoundError as e:
            LOG.error(f"Error opening {user_data['path']}: {e}")
            if not dpg.does_item_exist(f"{work_id}_window"):
                return
            dpg.configure_item(f"{work_id}_status_text", color=(255, 0, 0))
            dpg.set_value(
                f"{work_id}_status_text", f"File was deleted or moved",
            )
            dpg.configure_item(f"{work_id}_open_button", show=False)
        except Exception as e:
            LOG.error(f"Error opening {user_data['path']}: {e}")
            dpg.configure_item(f"{work_id}_status_text", color=(255, 0, 0))
            dpg.set_value(
                f"{work_id}_status_text", f"Error opening file",
            )
            dpg.configure_item(f"{work_id}_open_button", show=False)    

    def _remove_work_item(self, sender=None, data=None, user_data=None) -> None:
        """Callback for clicking the X button on a work.

        Remove this work from the UI and also tell the engine to remove it.
        """
        work_id = user_data["work_id"]
        window_tag = f"{work_id}_window"
        if dpg.does_item_exist(window_tag):
            dpg.delete_item(window_tag)
        self.engine.remove(work_id)

    def _remove_all(self, sender=None, data=None) -> None:
        """Callback for clicking the X button on a work.

        Remove all works currently staged.
        """
        dpg.delete_item("works_window", children_only=True)
        self.engine.remove_all()

    def _show_work_item_downloading(self, work_id: int) -> None:
        """Shows a work item as downloading.

        This will hide the 'open' button and set the status text to indicate
        that it is downloading.
        """
        window_tag = f"{work_id}_window"
        if not dpg.does_item_exist(window_tag):
            return

        dpg.configure_item(f"{work_id}_loading", show=True)
        dpg.configure_item(f"{work_id}_open_button", show=False)
        dpg.configure_item(f"{work_id}_status_group", show=True)
        dpg.configure_item(f"{work_id}_status_text", color=(255, 255, 0))
        dpg.set_value(
            f"{work_id}_status_text", f"Downloading...",
        )

    def _show_work_item_loading(self, work_id: int) -> None:
        """Shows a work item as loading.

        This will create a UI element for the work if it does not already exist
        or simply show/hide the sub-elements and disable the buttons if the
        element already exists.
        """
        window_tag = f"{work_id}_window"
        if not dpg.does_item_exist(window_tag):
            return

        dpg.configure_item(f"{work_id}_loading", show=True)
        dpg.configure_item(f"{work_id}_title_group", show=False)
        dpg.configure_item(f"{work_id}_metadata_group", show=False)
        dpg.configure_item(f"{work_id}_status_group", show=True)
        dpg.configure_item(f"{work_id}_status_text", color=(255, 255, 0), show=True)
        dpg.set_value(
            f"{work_id}_status_text", f"Loading...",
        )

    def _update_work_item_metadata(self, work_id: int, work: Work) -> None:
        """Update the metadata displayed in the UI for this work."""
        if not work.loaded:
            return

        dpg.configure_item(f"{work_id}_title_group", show=True)
        dpg.configure_item(f"{work_id}_metadata_group", show=True)
        dpg.set_value(f"{work_id}_title", f"{work.title}")
        authors = ", ".join(author.strip() for author in work.metadata["authors"])
        dpg.set_value(f"{work_id}_author", f"Author(s): {authors}")
        dpg.set_value(
            f"{work_id}_chapters",
            f"Chapters: {work.metadata['nchapters']}/{work.metadata['expected_chapters'] or '?'}",
        )
        dpg.set_value(f"{work_id}_words", f"Words: {work.metadata['words']}")
        dpg.set_value(
            f"{work_id}_date_edited", f"Edited: {work.metadata['date_edited'].strip()}"
        )

    def _update_work_item_after_load(
        self, work_id: int, data: Optional[WorkItem] = None, error: Optional[str] = None
    ) -> None:
        """Callback to be called by the engine.

        When the engine completes loading of a work (which may be in another 
        thread), this function will be called to update the placeholder item
        with the real work metadata.

        If an error occurs, an error message will be printed.
        """
        if not dpg.does_item_exist(f"{work_id}_window"):
            return

        if not data or error:
            error = error or "unknown"
            dpg.configure_item(
                # This is hacky. TODO: make this more robus
                f"{work_id}_loading",
                show="rate limit" in error,
            )
            dpg.configure_item(f"{work_id}_title_group", show=False)
            dpg.configure_item(f"{work_id}_metadata_group", show=False)
            dpg.configure_item(f"{work_id}_status_group", show=True)
            dpg.configure_item(f"{work_id}_status_text", color=(255, 0, 0))
            dpg.set_value(f"{work_id}_status_text", f"Load error: {error}")
            return

        dpg.configure_item(f"{work_id}_loading", show=False)
        self._update_work_item_metadata(work_id, data.work)
        dpg.configure_item(f"{work_id}_status_group", show=False)

    def _update_work_item_after_download(
        self, work_id: int, data: Optional[WorkItem] = None, error: Optional[str] = None
    ) -> None:
        """Callback to be called by the engine.

        When the engine completes downloading of a work (which may be in another 
        thread), this function will be called to show the open button and
        update the download status text.

        If an error occurs, the error message will be printed.
        """
        if not dpg.does_item_exist(f"{work_id}_window"):
            return

        if not (data and data.download_path) or error:
            error = error or "unknown"
            dpg.configure_item(
                # This is hacky. TODO: make this more robus
                f"{work_id}_loading",
                show="rate limit" in error,
            )
            dpg.configure_item(f"{work_id}_open_button", show=False)
            dpg.configure_item(f"{work_id}_status_group", show=True)
            dpg.configure_item(f"{work_id}_status_text", color=(255, 0, 0))
            dpg.set_value(
                f"{work_id}_status_text", f"Download error: {error}",
            )
            return

        dpg.configure_item(f"{work_id}_loading", show=False)
        dpg.configure_item(f"{work_id}_status_group", show=True)
        dpg.configure_item(f"{work_id}_status_text", color=(0, 255, 0))
        dpg.set_value(f"{work_id}_status_text", f"Downloaded to: {data.download_path}")
        dpg.set_item_user_data(f"{work_id}_open_button", {"work_id": work_id, "path": data.download_path})
        dpg.configure_item(f"{work_id}_open_button", show=True)

    def _show_user_input_dialog(self, sender=None, data=None, user_data=None) -> None:
        """Callback for when certain 'add <foo>' buttons are clicked.

        Displays a small popup window with a multiline textbox where users can
        enter text.
        """
        if dpg.does_item_exist("user_input_dialog"):
            dpg.delete_item("user_input_dialog")

        with dpg.window(
            label=f"Add {user_data['add_type']}",
            tag="user_input_dialog",
            width=600,
            height=300,
            pos=(
                (dpg.get_viewport_width() - 600) // 2,
                (dpg.get_viewport_height() - 300) // 2,
            ),
        ):
            dpg.add_text(
                f"Enter {user_data['input_type']} on a new line each:",
                tag="user_input_dialog_text",
            )
            dpg.add_input_text(tag="user_input", multiline=True, width=580, height=200)
            dpg.add_button(
                label="OK",
                tag="submit_user_input_button",
                small=True,
                callback=self._submit_user_input,
                user_data=user_data,
            )

    def _submit_user_input(self, sender=None, data=None, user_data=None) -> None:
        """Callback for when the OK button is clicked on the add dialog.

        This will call the appropriate function to load works depending on
        what the caller was.
        """

        # TODO: add an error message if some works in list couldn't be loaded
        items = set(
            filter(
                None, [line.strip() for line in dpg.get_value("user_input").split("\n")]
            )
        )
        if dpg.does_item_exist("user_input_dialog"):
            dpg.delete_item("user_input_dialog")

        dpg.configure_item("add_works_status_text", color=(255, 255, 0), show=True)
        dpg.set_value("add_works_status_text", "Loading...")

        # TODO: generalize this to either work for all types of URLs, or support
        # IDs or URLs in the list.
        work_ids = set()
        add_type = user_data["add_type"]
        if add_type == "works":
            work_ids = self.engine.urls_to_work_ids(items)
        elif add_type == "series":
            work_ids = self.engine.series_urls_to_work_ids(items)
        elif add_type == "user works":
            work_ids = self.engine.usernames_to_work_ids(items)
        elif add_type == "user bookmarks":
            work_ids = self.engine.usernames_to_bookmark_ids(items)

        for work_id in work_ids:
            self._make_placeholder_work_item(work_id)
        self.engine.load_works(work_ids)

        dpg.configure_item("add_works_status_text", color=(255, 255, 0), show=False)

    def _add_self_bookmarks(self, sender=None, data=None) -> None:
        """Callback for when the add bookmarks button is clicked.

        Calls the engine to get all bookmarks and attempt to load them all.
        """
        if not self.engine.session.is_authed:
            dpg.configure_item("add_works_status_text", color=(255, 0, 0), show=True)
            dpg.set_value("add_works_status_text", "Not logged in!")
            return

        dpg.configure_item("add_works_status_text", color=(255, 255, 0), show=True)
        dpg.set_value("add_works_status_text", "Loading...")

        work_ids = self.engine.get_self_bookmarks()
        for work_id in work_ids:
            self._make_placeholder_work_item(work_id)
        self.engine.load_works(work_ids)

        dpg.configure_item("add_works_status_text", color=(255, 255, 0), show=False)

    def _download_all(self, sender=None, data=None) -> None:
        """Callback for when the download all button is clicked.

        Calls the engine to attempt download for all IDs staged right now.
        """
        self.engine.download_all()

    def _make_gui(self) -> None:
        """Create the layout for the entire application."""
        with dpg.window(label="ao3d", tag="primary_window"):
            with dpg.tab_bar(tag="tabs"):
                self._make_settings_tab()
                self._make_downloads_tab()

    def _make_settings_tab(self) -> None:
        """Create the layout for the settings tab."""
        with dpg.tab(label="Settings", tag="settings_tab"):
            with dpg.child_window(
                tag="settings_child_window", width=600, height=600,
            ):
                with dpg.group(tag="login_settings_group"):
                    dpg.add_text("AO3 Login", tag="login_settings_text")
                    with dpg.group(tag="username_group", horizontal=True):
                        dpg.add_text("Username:", tag="username_text")
                        dpg.add_input_text(
                            tag="username_input",
                            default_value=self.engine.config.username,
                        )
                    with dpg.group(tag="password_group", horizontal=True):
                        dpg.add_text("Password:", tag="password_text")
                        dpg.add_input_text(
                            tag="password_input",
                            password=True,
                            default_value=self.engine.config.password,
                        )
                    dpg.add_spacer(tag="login_button_spacer")
                    with dpg.group(tag="login_button_group", horizontal=True):
                        dpg.add_button(
                            label="Login",
                            tag="login_button",
                            small=True,
                            callback=self._login,
                        )
                        dpg.add_button(
                            label="Logout",
                            tag="logout_button",
                            small=True,
                            callback=self._logout,
                        )
                        dpg.add_text(
                            "", tag="login_status_text", show=False, indent=200
                        )
                        if self.engine.config.username or self.engine.config.password:
                            self._set_status_text_conditionally(
                                "login_status_text",
                                # Since this function compares if result == 0
                                not self.engine.session.is_authed,
                                f"Logged in as: {self.engine.session.username}",
                                "Not logged in",
                            )

                    dpg.add_checkbox(
                        label="Remember me?",
                        tag="remember_me_checkbox",
                        default_value=any(
                            (self.engine.config.username, self.engine.config.password)
                        ),
                    )
                dpg.add_spacer(tag="login_group_spacer", height=20)

                with dpg.group(tag="download_settings_group"):
                    dpg.add_text("Downloads", tag="download_settings_text")
                    with dpg.group(tag="downloads_dir_group", horizontal=True):
                        dpg.add_text("Directory:", tag="downloads_dir_text")
                        dpg.add_input_text(
                            tag="downloads_dir_input",
                            default_value=self.engine.config.downloads_dir.resolve(),
                        )
                        dpg.add_button(
                            label="Browse",
                            tag="downloads_dir_dialog_button",
                            callback=self._show_downloads_dir_dialog,
                            small=True,
                        )
                    with dpg.group(tag="filetype_group", horizontal=True):
                        dpg.add_text("Filetype:", tag="filetype_text")
                        dpg.add_combo(
                            items=list(constants.VALID_FILETYPES),
                            tag="filetype_combo",
                            default_value=constants.DEFAULT_DOWNLOADS_FILETYPE,
                            width=50,
                        )
                dpg.add_spacer(tag="download_settings_group_spacer", height=20)

                with dpg.group(tag="engine_settings_group"):
                    dpg.add_text("Engine", tag="engine_settings_text")
                    with dpg.group(tag="use_threading_group", horizontal=True):
                        dpg.add_text("Use threading?", tag="use_threading_text")
                        dpg.add_checkbox(
                            tag="use_threading_checkbox",
                            default_value=self.engine.config.should_use_threading,
                        )
                    with dpg.group(tag="concurrency_limit_group", horizontal=True):
                        dpg.add_text("Concurrency limit:", tag="concurrency_limit_text")
                        dpg.add_input_int(
                            tag="concurrency_limit_input",
                            default_value=self.engine.config.concurrency_limit,
                            min_value=1,
                            max_value=50,
                            min_clamped=True,
                            max_clamped=True,
                        )
                    with dpg.group(tag="rate_limit_group", horizontal=True):
                        dpg.add_text("Use rate limiting?", tag="rate_limit_text")
                        dpg.add_checkbox(
                            tag="rate_limit_checkbox",
                            default_value=self.engine.config.should_rate_limit,
                        )
                dpg.add_spacer(tag="engine_settings_group_spacer", height=20)
                with dpg.group(tag="save_settings_group", horizontal=True):
                    dpg.add_button(
                        label="Save settings",
                        tag="save_settings_button",
                        callback=self._save_settings,
                    )
                    dpg.add_button(
                        label="Reset",
                        tag="reset_settings_button",
                        callback=self._reset_settings,
                    )
                    dpg.add_text("", tag="settings_status_text", indent=200, show=False)

    def _make_downloads_tab(self) -> None:
        """Create the layout for the downloads tab."""
        with dpg.tab(label="Downloads", tag="downloads_tab"):
            dpg.add_spacer(tag="add_works_top_spacer", height=20)
            with dpg.group(tag="add_works_buttons", horizontal=True):
                dpg.add_text("Add works to download: ", tag="add_works_text")
                dpg.add_spacer(width=20)
                dpg.add_button(
                    label="Add bookmarks",
                    tag="add_bookmarks_button",
                    callback=self._add_self_bookmarks,
                )
                dpg.add_button(
                    label="Add works",
                    tag="add_works_button",
                    callback=self._show_user_input_dialog,
                    user_data={"add_type": "works", "input_type": "URLs"},
                )
                dpg.add_button(
                    label="Add series",
                    tag="add_series_button",
                    callback=self._show_user_input_dialog,
                    user_data={"add_type": "series", "input_type": "URLs"},
                )
                dpg.add_button(
                    label="Add user works",
                    tag="add_user_works_button",
                    callback=self._show_user_input_dialog,
                    user_data={"add_type": "user works", "input_type": "usernames"},
                )
                dpg.add_button(
                    label="Add user bookmarks",
                    tag="add_user_bookmarks_button",
                    callback=self._show_user_input_dialog,
                    user_data={"add_type": "user bookmarks", "input_type": "usernames"},
                )
                dpg.add_spacer(width=50)
                dpg.add_text(tag="add_works_status_text", show=False)
            dpg.add_spacer(tag="works_group_spacer")
            dpg.add_child_window(tag="works_window", autosize_x=True, height=610)
            with dpg.child_window(
                tag="downloads_footer",
                border=False,
                autosize_x=True,
                autosize_y=True,
                no_scrollbar=True,
            ):
                with dpg.group(tag="downloads_footer_group", horizontal=True):
                    dpg.add_button(
                        label="Download all",
                        tag="download_button",
                        height=50,
                        width=100,
                        callback=self._download_all,
                    )
                    dpg.add_button(
                        label="Remove all",
                        tag="remove_all_button",
                        height=50,
                        width=100,
                        callback=self._remove_all,
                    )
                    dpg.add_spacer(width=40)
                    with dpg.group(tag="downloads_footer_text_group"):
                        dpg.add_spacer(height=12)
                        dpg.add_text(tag="download_status_text", show=False)

    def _make_placeholder_work_item(self, work_id: int) -> None:
        """Creates the default placeholder item for a work.
        """
        if dpg.does_item_exist(f"{work_id}_window"):
            return

        with dpg.child_window(
            tag=f"{work_id}_window", parent="works_window", autosize_x=True, height=70
        ):
            with dpg.group(tag=f"{work_id}_group", horizontal=True):
                dpg.add_button(
                    label="X",
                    tag=f"{work_id}_remove_button",
                    width=50,
                    height=50,
                    callback=self._remove_work_item,
                    user_data={"work_id": work_id},
                )
                dpg.add_loading_indicator(tag=f"{work_id}_loading", show=True)
                dpg.add_button(
                    label="Open",
                    tag=f"{work_id}_open_button",
                    width=50,
                    height=50,
                    callback=self._open_file,
                    show=False,
                )
                dpg.add_spacer()
                with dpg.group(tag=f"{work_id}_content_group", horizontal=True):
                    with dpg.child_window(
                        tag=f"{work_id}_layout_left",
                        border=False,
                        width=dpg.get_viewport_width() - 120,
                        autosize_y=True,
                    ):
                        with dpg.group(tag=f"{work_id}_heading_group", horizontal=True):
                            dpg.add_text(f"{work_id}", tag=f"{work_id}_id")
                            with dpg.group(
                                tag=f"{work_id}_title_group",
                                horizontal=True,
                                show=False,
                            ):
                                dpg.add_spacer(width=30)
                                dpg.add_text(tag=f"{work_id}_title")
                            with dpg.group(
                                tag=f"{work_id}_status_group",
                                horizontal=True,
                                show=True,
                            ):
                                dpg.add_spacer(width=30)
                                dpg.add_text(tag=f"{work_id}_status_text")
                        with dpg.group(
                            tag=f"{work_id}_metadata_group", horizontal=True, show=False
                        ):
                            dpg.add_text(tag=f"{work_id}_author")
                            dpg.add_spacer(width=30)
                            dpg.add_text(tag=f"{work_id}_chapters")
                            dpg.add_spacer(width=30)
                            dpg.add_text(tag=f"{work_id}_words")
                            dpg.add_spacer(width=30)
                            dpg.add_text(tag=f"{work_id}_date_edited")
                            dpg.add_spacer(width=60)

    def _make_error_window(self):
        """Shows an error window.

        This will be shown if there is no running engine so the GUI cannot
        start as usual. This usually occurs if there was a rate limiting error.
        """
        with dpg.window(label="ao3d", tag="primary_window"):
            dpg.add_text("Hit rate limit :(\nPlease try again later.")
        dpg.configure_viewport("ao3d", width=200, height=100, resizable=False)

    def _setup_fonts(self) -> None:
        """Load additional fonts to be used in the GUI."""
        with dpg.font_registry():
            with dpg.font("resources/fonts/unifont-14.0.01.ttf", 16) as unifont:
                dpg.add_font_range(0x0080, 0x10FFFD)
        dpg.bind_font(unifont)

    def run(self) -> None:
        """Starts the GUI."""
        dpg.create_context()
        self._setup_fonts()

        dpg.create_viewport(title="ao3d", width=1280, height=800)
        dpg.setup_dearpygui()

        if self.engine:
            self._make_gui()
            dpg.set_exit_callback(self.engine.stop)
        else:
            self._make_error_window()
        dpg.set_primary_window("primary_window", True)

        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()

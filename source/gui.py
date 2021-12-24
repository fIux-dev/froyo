import dearpygui.dearpygui as dpg
import logging

from AO3 import Work
from pathlib import Path
from typing import Optional, Set, Tuple

from . import constants, utils
from .engine import Engine
from .configuration import Configuration

LOG = logging.getLogger(__name__)


def display_rate_limiting_error():
    dpg.create_context()
    dpg.create_viewport(title="Error", width=200, height=100, resizable=False)
    dpg.setup_dearpygui()
    with dpg.window(label="ao3d", tag="primary_window"):
        dpg.add_text("Hit rate limit :(\nPlease try again later.")
    dpg.show_viewport()
    dpg.set_primary_window("primary_window", True)
    dpg.start_dearpygui()
    dpg.destroy_context()


class GUI:
    engine: Engine

    _ids_to_download: Set[int]

    def __init__(self, engine: Engine):
        self.engine = engine
        self._ids_to_download = set()
        self._downloaded = set()

    # Callbacks
    def _set_status_label_conditionally(
        self,
        tag: str,
        result: int,
        success_text: str,
        error_text: str,
        success_color: Tuple[int, int, int] = (0, 255, 0),
        error_color: Tuple[int, int, int] = (255, 0, 0),
    ):
        color = error_color
        text = error_text
        if result == 0:
            color = success_color
            text = success_text
        dpg.set_value(tag, text)
        dpg.configure_item(tag, color=color, show=True)

    def _login(self, sender=None, data=None) -> None:
        dpg.configure_item("login_status_label", show=False)

        username = dpg.get_value("username_input")
        password = dpg.get_value("password_input")

        if not (username and password):
            return

        result = self.engine.login(username, password)
        self._set_status_label_conditionally(
            "login_status_label", result, "Logged in!", "Login error"
        )

    def _logout(self, sender=None, data=None) -> None:
        dpg.configure_item("login_status_label", show=False)

        dpg.set_value("username_input", "")
        dpg.set_value("password_input", "")

        result = self.engine.logout()
        self._set_status_label_conditionally(
            "login_status_label", result, "Logged out", "Logout error"
        )
        dpg.set_value("remember_me_checkbox", False)

    def _set_downloads_dir(self, sender=None, data=None) -> None:
        dpg.set_value("downloads_dir_input", data["file_path_name"])

    def _show_downloads_dir_dialog(self, sender=None, data=None) -> None:
        if dpg.does_item_exist("downloads_dir_dialog"):
            dpg.delete_item("downloads_dir_dialog")

        dpg.add_file_dialog(
            tag="downloads_dir_dialog",
            directory_selector=True,
            default_path=dpg.get_value("downloads_dir_input"),
            callback=self._set_downloads_dir,
        )

    def _save_settings(self, sender=None, data=None) -> None:
        dpg.configure_item("save_settings_status_label", show=False)

        config = Configuration()
        if dpg.get_value("remember_me_checkbox"):
            config.username = dpg.get_value("username_input")
            config.password = dpg.get_value("password_input")
        config.downloads_dir = Path(dpg.get_value("downloads_dir_input"))
        config.filetype = dpg.get_value("filetype_combo")
        config.should_use_threading = dpg.get_value("use_threading_checkbox")
        config.concurrency_limit = dpg.get_value("concurrency_limit_input")
        config.should_rate_limit = dpg.get_value("rate_limit_checkbox")
        self.engine.config = config
        result = self.engine.write_configuration_file(config)

        self._set_status_label_conditionally(
            "save_settings_status_label", result, "Saved!", "Save error"
        )

    def _remove_work_item(self, sender=None, data=None, user_data=None) -> None:
        work_id = user_data["work_id"]
        self.engine.remove(work_id)
        if work_id in self._ids_to_download:
            self._ids_to_download.remove(work_id)

        window_tag = f"{work_id}_window"
        if dpg.does_item_exist(window_tag):
            dpg.delete_item(window_tag)

    def _update_work_item_metadata(
        self, work_id: int, work: Optional[Work], update=True
    ) -> None:
        dpg.configure_item(f"{work_id}_loading", show=False)

        # Could not load work, show an error item
        window_tag = f"{work_id}_window"
        if not work:
            self._remove_work_item(user_data={"work_id": work_id})
            return

        if not dpg.does_item_exist(window_tag):
            return

        dpg.configure_item(f"{work_id}_group", show=True)
        if not update:
            return

        # TODO: update fonts to render properly
        dpg.set_value(f"{work_id}_title", f"{work_id}\t{work.title}")
        authors = ", ".join(author.strip() for author in work.metadata["authors"])
        dpg.set_value(f"{work_id}_author", f"Author(s): {authors}")
        dpg.set_value(
            f"{work_id}_chapters",
            f"Chapters: {work.metadata['nchapters']}/{work.metadata['expected_chapters']}",
        )
        dpg.set_value(f"{work_id}_words", f"Words: {work.metadata['words']}")
        dpg.set_value(
            f"{work_id}_date_edited", f"Edited: {work.metadata['date_edited'].strip()}"
        )

    def _show_placeholder_work_item(self, work_id: int) -> None:
        window_tag = f"{work_id}_window"
        if dpg.does_item_exist(window_tag):
            dpg.configure_item(f"{work_id}_loading", show=True)
            dpg.configure_item(f"{work_id}_group", show=False)
            return

        with dpg.child_window(
            tag=window_tag, parent="works_window", autosize_x=True, height=60
        ):
            dpg.add_loading_indicator(tag=f"{work_id}_loading")
            with dpg.group(tag=f"{work_id}_group", horizontal=True, show=False):
                dpg.add_button(
                    label="X",
                    tag=f"{work_id}_remove_button",
                    width=40,
                    height=40,
                    callback=self._remove_work_item,
                    user_data={"work_id": work_id},
                )
                dpg.add_loading_indicator(tag=f"{work_id}_download_loading", show=False)
                dpg.add_button(
                    label="Open",
                    tag=f"{work_id}_open_button",
                    width=40,
                    height=40,
                    callback=self._open_file,
                    show=False,
                )
                dpg.add_spacer()
                with dpg.child_window(
                    tag=f"{work_id}_layout_left",
                    border=False,
                    width=dpg.get_viewport_width() - 120,
                    autosize_y=True,
                ):
                    dpg.add_text(tag=f"{work_id}_title")
                    with dpg.group(tag=f"{work_id}_metadata_group", horizontal=True):
                        dpg.add_text(tag=f"{work_id}_author")
                        dpg.add_spacer(width=30)
                        dpg.add_text(tag=f"{work_id}_chapters")
                        dpg.add_spacer(width=30)
                        dpg.add_text(tag=f"{work_id}_words")
                        dpg.add_spacer(width=30)
                        dpg.add_text(tag=f"{work_id}_date_edited")
                        dpg.add_spacer(width=60)

    def _open_file(self, sender=None, data=None, user_data=None):
        utils.open_file(user_data["path"])

    def _show_download_loading_indicator(self, work_id: int):
        dpg.configure_item(f"{work_id}_download_loading", show=True)
        dpg.configure_item(f"{work_id}_open_button", show=False)

    def _update_work_item_after_download(
        self, work_id: int, path: Optional[Path], update=True
    ) -> None:
        dpg.configure_item(f"{work_id}_download_loading", show=False)
        if not path:
            dpg.configure_item(f"{work_id}_open_button", show=False)
            dpg.add_text(
                "Download error",
                tag=f"{work_id}_download_error_text",
                color=(255, 0, 0),
                parent=f"{work_id}_layout_right",
            )
            return

        if not update:
            return

        if dpg.does_item_exist(f"{work_id}_download_error_text"):
            dpg.delete_item(f"{work_id}_download_error_text")
        dpg.configure_item(f"{work_id}_open_button", show=True)
        dpg.set_item_user_data(f"{work_id}_open_button", {"path": path})
        self._downloaded.add(work_id)

    def _submit_urls(self, sender=None, data=None, user_data=None) -> None:
        # TODO: add an error message if some works in list couldn't be loaded
        add_type = user_data["add_type"]
        dpg.configure_item("urls_dialog", show=False)
        urls = set(
            filter(
                None, [url.strip() for url in dpg.get_value("urls_input").split("\n")]
            )
        )

        work_ids = set()
        if add_type == "works":
            work_ids = self.engine.work_urls_to_work_ids(urls)
        elif add_type == "series":
            # TODO: enable adding series
            pass

        self._ids_to_download.update(work_ids)
        for work_id in work_ids:
            self._show_placeholder_work_item(work_id)
        self.engine.load_works(work_ids, callback=self._update_work_item_metadata)

    def _show_urls_dialog(self, sender=None, data=None) -> None:
        add_type = ""
        if sender == "add_work_button":
            add_type = "works"
        elif sender == "add_series_button":
            add_type = "series"
        dpg.configure_item("urls_dialog", label=f"Add {add_type.title()}", show=True)
        dpg.set_item_user_data("submit_urls_button", {"add_type": add_type})
        dpg.set_value("urls_input", "")

    def _add_bookmarks(self, sender=None, data=None) -> None:
        if not self.engine.session.is_authed:
            dpg.configure_item(
                "add_bookmarks_status_label", color=(255, 0, 0), show=True
            )
            dpg.set_value("add_bookmarks_status_label", "Not logged in!")
            return

        dpg.configure_item("add_bookmarks_status_label", show=False)

        bookmark_ids = self.engine.get_bookmark_ids()
        self._ids_to_download.update(bookmark_ids)
        for work_id in bookmark_ids:
            self._show_placeholder_work_item(work_id)
        self.engine.load_works(bookmark_ids, callback=self._update_work_item_metadata)

        dpg.configure_item("add_bookmarks_status_label", color=(0, 255, 0), show=True)
        dpg.set_value("add_bookmarks_status_label", "Loaded bookmarks")

    def _download_all(self, sender=None, data=None) -> None:
        self._ids_to_download -= self._downloaded
        self.engine.download(
            self._ids_to_download, callback=self._update_work_item_after_download
        )

    # GUI setup functions
    def _make_gui(self) -> None:
        with dpg.window(
            label="ao3d", tag="primary_window"
        ):
            with dpg.tab_bar(tag="tabs"):
                self._make_settings_tab()
                self._make_downloads_tab()

    def _make_settings_tab(self) -> None:
        self.engine.parse_configuration_file()

        with dpg.tab(label="Settings", tag="settings_tab"):
            with dpg.child_window(
                tag="settings_child_window", width=500, height=410,
            ):
                with dpg.group(tag="login_settings_group"):
                    dpg.add_text("AO3 Login", tag="login_settings_label")
                    with dpg.group(tag="username_group", horizontal=True):
                        dpg.add_text("Username:", tag="username_label")
                        dpg.add_input_text(
                            tag="username_input",
                            default_value=self.engine.config.username,
                        )
                    with dpg.group(tag="password_group", horizontal=True):
                        dpg.add_text("Password:", tag="password_label")
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
                            "", tag="login_status_label", show=False, indent=200
                        )
                    dpg.add_checkbox(
                        label="Remember me?",
                        tag="remember_me_checkbox",
                        default_value=any(
                            (self.engine.config.username, self.engine.config.password)
                        ),
                    )
                dpg.add_spacer(tag="login_group_spacer", height=20)
                self._login()

                with dpg.group(tag="download_settings_group"):
                    dpg.add_text("Downloads", tag="download_settings_label")
                    with dpg.group(tag="downloads_dir_group", horizontal=True):
                        dpg.add_text("Directory:", tag="downloads_dir_label")
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
                        dpg.add_text("Filetype:", tag="filetype_label")
                        dpg.add_combo(
                            items=list(constants.VALID_FILETYPES),
                            tag="filetype_combo",
                            default_value=constants.DEFAULT_DOWNLOADS_FILETYPE,
                            width=50,
                        )
                dpg.add_spacer(tag="download_settings_group_spacer", height=20)

                with dpg.group(tag="engine_settings_group"):
                    dpg.add_text("Engine", tag="engine_settings_label")
                    with dpg.group(tag="use_threading_group", horizontal=True):
                        dpg.add_text("Use threading?", tag="use_threading_label")
                        dpg.add_checkbox(
                            tag="use_threading_checkbox",
                            default_value=self.engine.config.should_use_threading,
                        )
                    with dpg.group(tag="concurrency_limit_group", horizontal=True):
                        dpg.add_text(
                            "Concurrency limit:", tag="concurrency_limit_label"
                        )
                        dpg.add_input_int(
                            tag="concurrency_limit_input",
                            default_value=self.engine.config.concurrency_limit,
                        )
                    with dpg.group(tag="rate_limit_group", horizontal=True):
                        dpg.add_text("Use rate limiting?", tag="rate_limit_label")
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
                    dpg.add_text(
                        "", tag="save_settings_status_label", show=False, indent=200
                    )

    def _make_downloads_tab(self) -> None:
        with dpg.tab(label="Downloads", tag="downloads_tab"):
            dpg.add_spacer(tag="add_works_top_spacer", height=20)
            with dpg.group(tag="add_works_buttons", horizontal=True):
                dpg.add_text("Add works to download: ", tag="add_works_label")
                dpg.add_spacer(tag="add_works_buttons_hspacer")
                dpg.add_button(
                    label="Add works",
                    tag="add_work_button",
                    callback=self._show_urls_dialog,
                )
                # TODO: enable adding series
                # dpg.add_button(
                #     label="Add series",
                #     tag="add_series_button",
                #     callback=self._show_urls_dialog,
                # )
                dpg.add_button(
                    label="Add bookmarks",
                    tag="add_bookmarks_button",
                    callback=self._add_bookmarks,
                )
                dpg.add_spacer()
                dpg.add_text(tag="add_bookmarks_status_label", show=False)
            dpg.add_spacer(tag="works_group_spacer")
            dpg.add_child_window(tag="works_window", autosize_x=True, height=620)
            with dpg.child_window(
                tag="downloads_footer", border=False, autosize_x=True, autosize_y=True
            ):
                dpg.add_button(
                    label="Download all",
                    tag="download_button",
                    height=50,
                    width=100,
                    callback=self._download_all,
                )
            with dpg.window(
                label="Add URLs",
                tag="urls_dialog",
                width=600,
                height=300,
                pos=(
                    (dpg.get_viewport_width() - 600) // 2,
                    (dpg.get_viewport_height() - 300) // 2,
                ),
                show=False,
            ):
                dpg.add_text("Enter URLs on a new line each:", tag="urls_dialog_label")
                dpg.add_input_text(
                    tag="urls_input", multiline=True, width=580, height=200
                )
                dpg.add_button(
                    label="OK",
                    tag="submit_urls_button",
                    small=True,
                    callback=self._submit_urls,
                )

    def run(self) -> None:
        dpg.create_context()
        dpg.create_viewport(
            title="ao3d")
        dpg.setup_dearpygui()
        self._make_gui()
        dpg.set_primary_window("primary_window", True)
        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()

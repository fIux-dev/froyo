import configparser
import logging
import os

from pathlib import Path

from . import constants

LOG = logging.getLogger(__name__)


class Configuration:
    username: str
    password: str
    downloads_dir: Path
    filetype: str
    should_use_threading: bool
    concurrency_limit: int
    should_rate_limit: bool

    _filename: Path

    def __init__(self, filename: Path):
        self.username = ""
        self.password = ""
        self.downloads_dir = Path.home() / constants.DEFAULT_DOWNLOADS_DIR
        self.filetype = constants.DEFAULT_DOWNLOADS_FILETYPE
        self.should_use_threading = True
        self.concurrency_limit = constants.DEFAULT_CONCURRENCY_LIMIT
        self.should_rate_limit = False

        self._filename = filename
        if not self._filename.is_file():
            LOG.info(f"No existing configuration file found, "
                f"writing default configuration to: {self._filename.resolve()}")
            self.write_to_file()
        else:
            self.parse_from_file()

    def parse_from_file(self) -> int:
        try:
            LOG.info(
                f"Found existing configuration file at: "
                f"{self._filename.resolve()}"
            )

            parsed_config = configparser.ConfigParser()
            parsed_config.read(self._filename)

            if (
                "credentials" in parsed_config
                and "username" in parsed_config["credentials"]
            ):
                self.username = parsed_config["credentials"]["username"]

            if (
                "credentials" in parsed_config
                and "password" in parsed_config["credentials"]
            ):
                self.password = parsed_config["credentials"]["password"]

            if "downloads" in parsed_config and "directory" in parsed_config["downloads"]:
                self.downloads_dir = Path(parsed_config["downloads"]["directory"])

            if "downloads" in parsed_config and "filetype" in parsed_config["downloads"]:
                filetype = parsed_config["downloads"]["filetype"].upper()
                try:
                    assert filetype.upper() in constants.VALID_FILETYPES
                    self.filetype = filetype
                except Exception:
                    valid_filetypes_string = ", ".join(constants.VALID_FILETYPES)
                    LOG.error(
                        f"Invalid filetype specified in {self._filename}, "
                        f"valid types are: {valid_filetypes_string}. Using default "
                        f"filetype value of {constants.DEFAULT_DOWNLOADS_FILETYPE} "
                        f"instead."
                    )

            if (
                "engine" in parsed_config
                and "should_use_threading" in parsed_config["engine"]
            ):
                try:
                    self.should_use_threading = bool(
                        int(parsed_config["engine"]["should_use_threading"])
                    )
                except Exception:
                    LOG.error(
                        f"Invalid value specified for "
                        f"engine:should_use_threading, must be 0 or 1."
                    )

            if "engine" in parsed_config and "concurrency_limit" in parsed_config["engine"]:
                concurrency_limit = parsed_config["engine"]["concurrency_limit"]
                try:
                    self.concurrency_limit = int(concurrency_limit)
                    assert self.concurrency_limit > 0
                except Exception:
                    LOG.error(
                        f"Invalid value {concurrency_limit} specified for "
                        f"concurrency limit, must be an integer >= 1. Using "
                        f"default value of {constants.DEFAULT_CONCURRENCY_LIMIT} "
                        f"instead."
                    )

            if "engine" in parsed_config and "should_rate_limit" in parsed_config["engine"]:
                try:
                    self.should_rate_limit = bool(
                        int(parsed_config["engine"]["should_rate_limit"])
                    )
                except Exception:
                    LOG.error(
                        f"Invalid value specified for "
                        f"engine:should_rate_limit, must be 0 or 1."
                    )

            LOG.info(f"Done parsing existing configuration.")
            return 0
        except Exception as e:
            LOG.error(f"Unhandled error while parsing configuration file "
                f"at {self._filename}: {e}. Default configuration will be "
                "used.")
            return 1

    def write_to_file(self) -> int:
        try:
            LOG.info(f"Writing configuration to: {self._filename.resolve()}")
            with open(self._filename, "w") as f:
                f.write(
                    constants.CONFIGURATION_FILE_TEMPLATE.format(
                        self.username,
                        self.password,
                        self.downloads_dir.resolve(),
                        self.filetype,
                        int(self.should_use_threading),
                        self.concurrency_limit,
                        int(self.should_rate_limit),
                    )
                )
            LOG.info("Successfully wrote configuration file.")
            return 0
        except Exception:
            return 1
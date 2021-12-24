from pathlib import Path

from . import constants


class Configuration:
    username: str
    password: str
    downloads_dir: Path
    filetype: str
    should_use_threading: bool
    concurrency_limit: int
    should_rate_limit: bool

    def __init__(self):
        self.username = ""
        self.password = ""
        self.downloads_dir = Path(constants.DEFAULT_DOWNLOADS_DIR)
        self.filetype = constants.DEFAULT_DOWNLOADS_FILETYPE
        self.should_use_threading = True
        self.concurrency_limit = constants.DEFAULT_CONCURRENCY_LIMIT
        self.should_rate_limit = False

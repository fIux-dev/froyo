import logging
import os
import subprocess

from pathlib import Path
from typing import Optional

LOG = logging.getLogger(__name__)


def open_file(filename: Path):
    """Attempt to open file with default system application. Cross-platform."""
    LOG.info(f"Trying to open {filename} in default system application...")
    try:
        os.startfile(str(filename))
    except AttributeError:
        subprocess.call(["open", str(filename)])

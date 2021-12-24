import os
import subprocess

from pathlib import Path


def open_file(filename: Path):
    """Attempt to open file with default system application. Cross-platform."""
    try:
        os.startfile(str(filename))
    except AttributeError:
        subprocess.call(["open", str(filename)])

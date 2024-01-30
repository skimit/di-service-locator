# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""Some file utilities."""
from pathlib import Path
from typing import Sequence

DI_CONFIG_DIR = ".di"
HOME_DIR = Path.home() / DI_CONFIG_DIR
CURRENT_DIR = Path().absolute()
CURRENT_OR_HOME = [CURRENT_DIR, HOME_DIR]
# An ordered list of preferred file locations


class FileLocator:
    """Finds files using path precedences."""

    def __init__(self, paths: Sequence[Path]) -> None:
        """
        Constructor.

        :param paths: ordered set of paths to search for files
        """
        self._paths = paths

    def find_file(self, file_name: str) -> Path:
        """
        Find a file in the list of paths.  First found is returned.

        :param file_name: the name of the file to find
        :returns: the path to the found file
        """

        for path in self._paths:
            potential = path / file_name
            if potential.exists() and potential.is_file():
                return potential

        error_msg = f"{file_name} doesn't exist in '{self._paths}'"
        raise FileNotFoundError(error_msg)

    @staticmethod
    def find(paths: Sequence[Path], file_name: str) -> Path:
        """
        Static find method that takes paths and a file name.

        :param paths: list of paths
        :param file_name: the file name to find
        :returns: the found file path
        """
        return FileLocator(paths).find_file(file_name)

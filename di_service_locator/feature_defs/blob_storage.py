# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""Module for basic blob storage implementations."""
import contextlib
from pathlib import Path
from typing import IO, Generator, Tuple

from typing_extensions import Self

from di_service_locator.feature_defs.instrumentation import instrument_timer
from di_service_locator.feature_defs.interfaces import (
    Blob,
    BlobNotFoundError,
    BlobStorage,
    BlobStorageError,
    DeletableBlobStorage,
    Key,
)


class FileBlob(Blob):
    """
    File implementation of `Blob`.

    Provides ability to stream file contents on demand.
    """

    def __init__(self, key: Key, file: Path) -> None:
        """
        Constructor.

        :param key: the blob store key
        :type key: Key
        :param file: the file containing the blob
        :type file: Path
        """
        self._key = key
        self._file = file

    @property
    def key(self) -> Key:
        """Key of the blob"""
        return self._key

    @contextlib.contextmanager
    def stream(self) -> Generator[IO[bytes], None, None]:
        """A read only stream of the blob content"""
        try:
            ret = self._file.open(mode="rb")
            try:
                yield ret
            finally:
                ret.close()
        except IOError as ex:
            raise BlobStorageError(f"Error streaming blob {self._key}") from ex

    def __repr__(self) -> str:
        """Repr for blob"""
        return f"FileBlob {{key={self._key}}}"


DEFAULT_BUFFER_SIZE = 1024


class FileBlobStorage(BlobStorage):
    """File `BlobStorage` implementation."""

    # TODO: readonly flag?
    def __init__(self, root_path: str, buffer_size: int = DEFAULT_BUFFER_SIZE) -> None:
        """
        Constructor.

        :param root_path: the root path location where the store is located
        :type root_path: str
        :param buffer_size: size of byte buffer to use when transferring data,
            defaults to DEFAULT_BUFFER_SIZE
        :type buffer_size: int, optional
        :raises BlobStorageError: if the root path doesn't exist or is not a directory
        """
        self._root_path = Path(root_path)
        self._buffer_size = buffer_size

        if self._root_path.is_file():
            raise BlobStorageError(
                f"Root path '{root_path}' is not valid directory for {self.__class__.__name__}"
            )

        if not self._root_path.is_dir():
            raise BlobStorageError(f"'{root_path}' refers to a location that doesn't exist.")

    @instrument_timer
    def __iter__(self) -> Generator[Blob, None, None]:
        try:
            for file in self._root_path.glob("**/*"):
                if file.is_file():
                    yield FileBlob(key=f"/{str(file.relative_to(self._root_path))}", file=file)
        except IOError as ex:
            raise BlobStorageError(
                f"Error listing contents of {self.__class__.__name__} with root "
                f"'{self._root_path}'"
            ) from ex

    @instrument_timer
    def put(self, key: Key, data: IO[bytes]) -> None:
        # TODO: may need override flag for updates
        location, file = self._key_to_location_and_file(key)
        try:
            location.mkdir(parents=True, exist_ok=True)
            with file.open(mode="wb") as file_pointer:
                while True:
                    buffer = data.read(self._buffer_size)
                    if buffer:
                        file_pointer.write(buffer)
                    else:
                        break
        except IOError as ex:
            raise BlobStorageError(f"Error putting data with key '{key}'") from ex

    @contextlib.contextmanager
    def putter(self, key: Key) -> Generator[IO[bytes], None, None]:
        # TODO: may need override flag for updates
        location, file = self._key_to_location_and_file(key)
        try:
            location.mkdir(parents=True, exist_ok=True)
            ret = file.open(mode="wb")
            try:
                yield ret
            finally:
                ret.close()
        except IOError as ex:
            raise BlobStorageError(f"Error creating putter for key '{key}'") from ex

    def _key_to_location_and_file(self, key: Key) -> Tuple[Path, Path]:
        pieces = key.split("/")
        location: Path = self._root_path
        if len(pieces) > 1:
            path = pieces[:-1]
            for piece in path:
                location /= piece
        # resolve the file to remove any relative paths from keys
        file = (location / pieces[-1]).resolve()
        if self._root_path.resolve() not in file.parents:
            # if the resultant file is not within the root path of the store
            # then raise an error
            raise BlobStorageError(f"Invalid key '{key}'")
        return location, file

    @instrument_timer
    def get(self, key: Key) -> Blob:
        _, file = self._key_to_location_and_file(key)
        if (not file.exists()) or (not file.is_file()):
            raise BlobNotFoundError(f"Blob for key '{key}' does not exist")
        return FileBlob(key=f"/{str(file.relative_to(self._root_path.resolve()))}", file=file)

    @property
    def storage_id(self) -> str:
        return f"{self.__class__.__name__}[root_path='{self._root_path}']"

    def namespace(self, prefix: str) -> Self:
        _, namespaced_path = self._key_to_location_and_file(prefix)
        try:
            namespaced_path.mkdir(parents=True, exist_ok=True)
            return self.__class__(
                root_path=str(namespaced_path), buffer_size=self._buffer_size
            )
        except IOError as ex:
            raise BlobStorageError(
                f"Error namespacing {self.__class__.__name__} for namespace {prefix}"
            ) from ex


class DeletableFileBlobStorage(FileBlobStorage, DeletableBlobStorage):
    """Extension of `FileBlobStorage` with delete funcionality"""

    @instrument_timer
    def delete(self, key: Key) -> None:
        _, file = self._key_to_location_and_file(key)
        try:
            Path(file).unlink(missing_ok=True)
        except OSError as ex:
            if not file.is_dir():
                raise BlobStorageError(f"Error deleting blob {file}.") from ex

# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""
Contains common, simple service interface definitions.

It is not a requirement that all service definitions go in here, but it is a useful place
for most of them.
"""
import abc
from datetime import datetime
from typing import IO, ContextManager, Generator, Iterable

from typing_extensions import Self


class Instrumentation(abc.ABC):
    """
    Definition of instrumentation service.

    Instrumentation can be used to report on execution timings, counts and gauges.
    """

    @abc.abstractmethod
    def register_report(self, report_id: str) -> None:
        """
        Register a new thing that will be timed.

        :param report_id: An id to associate the timings with
        :type report_id: str
        """
        raise NotImplementedError  # pragma: no cover

    @abc.abstractmethod
    def register_gauge(self, gauge_id: str) -> None:
        """
        Register a new gauge.

        :param gauge_id: An id to associate the metric with
        :type gauge_id: str
        """
        raise NotImplementedError  # pragma: no cover

    @abc.abstractmethod
    def register_counter(self, counter_id: str) -> None:
        """
        Register a new counter.

        :param counter_id: An id to associate the metric with
        :type counter_id: str
        """
        raise NotImplementedError  # pragma: no cover

    @abc.abstractmethod
    def report(self, report_id: str, start_time: datetime, end_time: datetime) -> None:
        """
        Report an execution timing.

        :param report_id: An id to associate the timings with
        :type report_id: str
        :param start_time: the start time of execution
        :type start_time: datetime
        :param end_time: the end time of execution
        :type end_time: datetime
        """
        raise NotImplementedError  # pragma: no cover

    @abc.abstractmethod
    def update_gauge(self, gauge_id: str, delta: float) -> None:
        """
        Report a change to a gauge.

        :param gauge_id: An id to associate the metric with
        :type gauge_id: str
        :param delta: the change to the metric
        :type delta: float
        """
        raise NotImplementedError  # pragma: no cover

    @abc.abstractmethod
    def increase_counter(self, counter_id: str, increase: int) -> None:
        """
        Report an increase to a counter.

        :param counter_id: An id to associate the metric with
        :type counter_id: str
        :param increase: the change to the metric, must be positive
        :type increase: int
        :raises ValueError: if `increase` is negative
        """
        raise NotImplementedError  # pragma: no cover


Key = str


class BlobStorageError(Exception):
    """Error raised when an error occurs using the `BlobStorage` service."""


class BlobNotFoundError(BlobStorageError):
    """Error raised when a file cannot be found in the `BlobStorage` service."""


class Blob(abc.ABC):
    """
    A blob pointer obtained from the `BlobStorage` service.

    This pointer exposes the key of the blob and a stream of the binary data can be accessed.

    Example:
        Once a blob has been obtained from a blob storage implementation, the data can be read
        from within a context manager accessing the stream method::

            blob = blob_storage.get(key)
            with blob.stream() as st:
                data = st.read()
    """

    @property
    @abc.abstractmethod
    def key(self) -> Key:
        """The key with which this blob is referenced in the `BlobStorage` implementation."""
        raise NotImplementedError  # pragma: no cover

    @abc.abstractmethod
    def stream(self) -> ContextManager[IO[bytes]]:
        """
        Access a stream of the blob data within a context manager.

        :raises BlobStorageError: if an error occurs trying to access the byte data
        """
        raise NotImplementedError  # pragma: no cover


class BlobStorage(Iterable[Blob]):
    """
    Conceptual definition of a simple blob storage service.

    Blob storage is a very basic service to store and retrieve blobs of data.
    It could be implemented using the file system, a cloud bucket, a database,
    in memory or anything that can handle binary data.
    The storage has an implicit folder structure in the fact that keys can (and will ofter)
    look like paths.  For example '/root/folder1/blob.png'
    """

    @abc.abstractmethod
    def __iter__(self) -> Generator[Blob, None, None]:
        """
        Provide an iterator over the contents of the storage.

        No blob data is read during this operation, only pointers to the blob data are
        returned.

        Example:
            blob_storage = ServiceLocator.service(BlobStorage)
            for blob in blob_storage:
                ...

        :raises BlobStorageError: if an error occurs accessing the storage
        :return: the `Blob`s representing all of the data in the storage
        :rtype: Generator[Blob, None, None]
        """
        raise NotImplementedError  # pragma: no cover

    @abc.abstractmethod
    def put(self, key: Key, data: IO[bytes]) -> None:
        """
        Store some data in the storage.

        :param key: the key to where the data should be stored
        :type key: Key
        :param data: the stream of binary data to store
        :type data: IO[bytes]
        :raises BlobStorageError: if an error occurs storing the data
        """
        raise NotImplementedError  # pragma: no cover

    @abc.abstractmethod
    def putter(self, key: Key) -> ContextManager[IO[bytes]]:
        """
        Obtain a byte stream to write data directly into the storage.

        Note that it must be a byte stream that is written.  Conversion functions
        are availble in `di_service_locator.utils.transcoding` for converting text streams
        to byte streams a vice versa.

        Example:
            Streaming JSON directly to the storage::

                import json
                from di_service_locator.utils.transcoding import text_to_bytes_writer

                bs = ServiceLocator.service(BlobStorage)
                with bs.putter("config.json") as pt:
                    json.dump({"key": 5}, text_to_bytes_writer(pt))

        :param key: the key specifiying where the blob should be stored
        :type key: Key
        :raises BlobStorageError: if an error occurs creating the putter
        :return: a byte stream to write the data into
        :rtype: ContextManager[IO[bytes]]
        """
        raise NotImplementedError  # pragma: no cover

    @abc.abstractmethod
    def get(self, key: Key) -> Blob:
        """
        Retrieve a blob from storage.

        :param key: the key of the blob to retrieve
        :type key: Key
        :raises BlobNotFoundError if there is no blob for the specified key
        :raises BlobStorageError: if an error occurs retrieving the blob
        :return: a `Blob` object pointing to the blob data
        :rtype: Blob
        """
        raise NotImplementedError  # pragma: no cover

    @property
    @abc.abstractmethod
    def storage_id(self) -> str:
        """
        A string representing the source of data.

        This should include the type of storage implementation and any details regarding
        the configuration of the implementation.

        :return: the storage id
        :rtype: str
        """
        raise NotImplementedError  # pragma: no cover

    @abc.abstractmethod
    def namespace(self, prefix: str) -> Self:
        """
        Creates a namespaced instance of the underlying `BlobStorage`.

        This is a useful feature if a single storage instance contains multiple datasets or
        folders/directories of data.
        This method is the equivalent of doing a `cd` into the directory to work with the data
        contained within the folder.  Access to parent folders and files is then prohibited
        and only data and other folders contained within the namespace can be accessed.

        Example:
            storage = ServiceLocator.service(BlobStorage)
            dataset = storage.namespace(name_of_dataset_folder)

            # enumerate dataset
            for blob in dataset:
                handle_blob(blob)

        :raises BlobStorageError: if an error occurs creating the namespace
        """
        raise NotImplementedError  # pragma: no cover


class DeletableBlobStorage(BlobStorage):
    """Extension of a Blob storage to allow deletion of blobs."""

    @abc.abstractmethod
    def delete(self, key: Key) -> None:
        """
        Deletes a blob from storage

        :param key: the key of the blob to delete
        :type key: Key
        :raises BlobStorageError: if an error occurs deleting the blob
        """
        raise NotImplementedError  # pragma: no cover

    @abc.abstractmethod
    def namespace(self, prefix: str) -> Self:
        """
        Creates a namespaced instance of the underlying `DeletableBlobStorage`.

        NOTE: This override is a workaround for not being able to use `Self`.
        If we move to python 3.11 and update mypy we can use `Self` instead as per:
        https://peps.python.org/pep-0673/

        This is a useful feature if a single storage instance contains multiple datasets or
        folders/directories of data.
        This method is the equivalent of doing a `cd` into the directory to work with the data
        contained within the folder.  Access to parent folders and files is then prohibited
        and only data and other folders contained within the namespace can be accessed.

        Example:
            storage = ServiceLocator.service(DeletableBlobStorage)
            dataset = storage.namespace(name_of_dataset_folder)

            # enumerate dataset
            for blob in dataset:
                handle_blob(blob)

        :raises BlobStorageError: if an error occurs creating the namespace
        """
        raise NotImplementedError  # pragma: no cover

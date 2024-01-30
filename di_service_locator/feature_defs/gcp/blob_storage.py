# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""
Google cloud bucket blob storage implementation of BlobStorage.

Sadly the python API doesn't support streaming so we occasionally have to buffer data
in memory.
"""
import contextlib
import io
import os
from typing import IO, Generator, Optional

import google.api_core.exceptions as google_exceptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage
from typing_extensions import Self

from di_service_locator.feature_defs.instrumentation import instrument_timer
from di_service_locator.feature_defs.interfaces import (
    Blob,
    BlobNotFoundError,
    BlobStorage,
    BlobStorageError,
    Key,
)
from di_service_locator.files import CURRENT_OR_HOME, FileLocator

_ENV_GOOGLE_CREDS = "GOOGLE_APPLICATION_CREDENTIALS"
_DEFAULT_CREDS_FILE = "google_credentials.json"


class _GoogleBlob(Blob):
    """Google blob implementation for our Blob interface."""

    def __init__(
        self,
        google_blob: storage.Blob,
        client: storage.Client,
        namespace: Optional[str],
    ) -> None:
        self._google_blob = google_blob
        self._client = client
        self._namespace = namespace

    @property
    def key(self) -> Key:
        """
        Normalise the key to be prefixed with a /.

        Note: This is just to be consistent with other BlobStorage implementations.
        """
        # strip off namespace if we have one
        has_namespace_error = (
            self._namespace is not None
            and not self._google_blob.name.startswith(self._namespace)  # type: ignore
        )
        if has_namespace_error:
            raise BlobStorageError(
                f"Blob namespace '{self._namespace}' does not match blob name "
                f"'{self._google_blob.name}'"
            )
        stripped = (
            self._google_blob.name[len(self._namespace) + 1 :]  # type: ignore
            if self._namespace
            else self._google_blob.name
        )
        return f"/{stripped}"

    @contextlib.contextmanager
    def stream(self) -> Generator[IO[bytes], None, None]:
        # streaming is not supported by the python API :(
        data = io.BytesIO()
        try:
            self._client.download_blob_to_file(self._google_blob, data)
            data.seek(0)
        except google_exceptions.GoogleAPIError as error:
            raise BlobStorageError(f"Error streaming data for key '{self.key}'") from error
        yield data

    def __repr__(self) -> str:
        return f"_GoogleBlob {{key={self.key}}}"


class GoogleBucketBlobStorage(BlobStorage):
    """Google bucket implementation of `BlobStorage`."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        project_name: str,
        bucket_name: str,
        namespace: Optional[str] = None,
        anonymous: bool = False,
        creds_name: Optional[str] = None,
    ) -> None:
        if not anonymous:
            GoogleBucketBlobStorage._init_env(creds_name)
        self._project_name = project_name
        self._bucket_name = bucket_name
        self._client = storage.Client(
            project=project_name,
            credentials=AnonymousCredentials() if anonymous else None,
        )
        # sanitise prefix to remove leading / if there is one
        self._prefix = GoogleBucketBlobStorage._sanitise(namespace)
        self._anonymous = anonymous

    @staticmethod
    def _init_env(creds_name: Optional[str]):
        if _ENV_GOOGLE_CREDS not in os.environ:
            creds_file = FileLocator.find(
                CURRENT_OR_HOME, creds_name if creds_name else _DEFAULT_CREDS_FILE
            )
            if creds_file:
                os.environ[_ENV_GOOGLE_CREDS] = str(creds_file.absolute())

    @staticmethod
    def _sanitise(key: Optional[Key]) -> Optional[str]:
        if key is None:
            return None
        ret = key
        if ret.startswith("/"):
            ret = ret[1:]
        if ret.endswith("/"):
            ret = ret[:-1]
        return ret

    def _get_blob(self, key: Key) -> storage.Blob:
        bucket = self._client.get_bucket(self._bucket_name)
        namespaced_key = (
            f"{self._prefix}/{GoogleBucketBlobStorage._sanitise(key)}"
            if self._prefix
            else GoogleBucketBlobStorage._sanitise(key)
        )
        return storage.Blob(namespaced_key, bucket)

    @instrument_timer
    def __iter__(self) -> Generator[Blob, None, None]:
        try:
            for blob in self._client.list_blobs(
                bucket_or_name=self._bucket_name,
                prefix=f"{self._prefix}/" if self._prefix else None,
            ):
                yield _GoogleBlob(blob, client=self._client, namespace=self._prefix)
        except google_exceptions.GoogleAPIError as error:
            raise BlobStorageError(
                f"Error listing contents of bucket '{self._bucket_name}' "
                f"in project '{self._project_name}'"
            ) from error

    @instrument_timer
    def put(self, key: Key, data: IO[bytes]) -> None:
        try:
            blob = self._get_blob(key)
            blob.upload_from_file(data)
        except google_exceptions.GoogleAPIError as error:
            raise BlobStorageError(f"Error uploading data for key '{key}'") from error

    @contextlib.contextmanager
    def putter(self, key: Key) -> Generator[IO[bytes], None, None]:
        # again, no streaming support in python API so put data in a buffer
        buffer = io.BytesIO()
        yield buffer
        buffer.seek(0)
        self.put(key, buffer)

    @instrument_timer
    def get(self, key: Key) -> Blob:
        try:
            blob = self._get_blob(key)
            blob.reload()
            return _GoogleBlob(blob, client=self._client, namespace=self._prefix)
        except google_exceptions.NotFound as error:
            raise BlobNotFoundError(f"Blob for key '{key}' does not exist") from error
        except google_exceptions.GoogleAPIError as error:
            raise BlobStorageError(f"Error getting data for key '{key}'") from error

    @property
    def storage_id(self) -> str:
        return (
            f"GoogleBucketBlobStorage[project_name='{self._project_name}', "
            f"bucket_name='{self._bucket_name}', namespace='{self._prefix}']"
        )

    def namespace(self, prefix: str) -> Self:
        sanitised = GoogleBucketBlobStorage._sanitise(prefix)
        new_prefix = f"{self._prefix}/{sanitised}" if self._prefix else sanitised
        return self.__class__(
            project_name=self._project_name,
            bucket_name=self._bucket_name,
            namespace=new_prefix,
            anonymous=self._anonymous,
        )

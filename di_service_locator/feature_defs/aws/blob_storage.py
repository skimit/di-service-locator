# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""
Module for aws s3 bucket blob storage implementation.

Sadly the python API doesn't support streaming so we occasionally have to buffer data
in memory.
"""
import contextlib
import io
import os
from typing import IO, TYPE_CHECKING, Generator, Optional

import boto3
import botocore.exceptions
from botocore import UNSIGNED
from botocore.config import Config
from typing_extensions import Self

from di_service_locator import logger
from di_service_locator.feature_defs.instrumentation import instrument_timer
from di_service_locator.feature_defs.interfaces import (
    Blob,
    BlobNotFoundError,
    BlobStorage,
    BlobStorageError,
    DeletableBlobStorage,
    Key,
)
from di_service_locator.files import CURRENT_OR_HOME, FileLocator

if TYPE_CHECKING:
    from mypy_boto3_s3.service_resource import Object, S3ServiceResource
else:
    Object = object
    S3ServiceResource = object

_ENV_AWS_CREDS = "AWS_SHARED_CREDENTIALS_FILE"
_DEFAULT_CREDS_FILE = "credentials"


class _AwsBlob(Blob):
    """AWS blob implementation for our Blob interface."""

    def __init__(
        self,
        aws_blob: Object,
        client: S3ServiceResource,
        namespace: Optional[str],
    ) -> None:
        self._aws_blob = aws_blob
        self._client = client
        self._namespace = namespace

    @property
    def key(self) -> Key:
        """
        Normalise the key to be prefixed with a /.

        Note: This is just to be consistent with other BlobStorage implementations.
        """
        # strip off namespace if we have one
        assert self._namespace is None or self._aws_blob.key.startswith(self._namespace)
        stripped = (
            self._aws_blob.key[len(self._namespace) + 1 :]
            if self._namespace
            else self._aws_blob.key
        )
        return f"/{stripped}"

    @contextlib.contextmanager
    def stream(self) -> Generator[IO[bytes], None, None]:
        try:
            streaming_body = self._aws_blob.get()["Body"]
            try:
                # The following implements read() but not seek()
                yield streaming_body  # type: ignore
            finally:
                streaming_body.close()
        except botocore.exceptions.ClientError as error:
            raise BlobStorageError(f"Error streaming data for key '{self.key}'") from error

    def __repr__(self) -> str:
        return f"_AwsBlob {{key={self.key}}}"


class AwsBucketBlobStorage(BlobStorage):
    """AWS bucket implementation of `BlobStorage`."""

    def __init__(
        self,
        bucket_name: str,
        namespace: Optional[str] = None,
        anonymous: bool = False,
        creds_name: Optional[str] = None,
    ) -> None:
        if not anonymous:
            AwsBucketBlobStorage._init_env(creds_name)
        self._bucket_name = bucket_name

        # If we want to use a different profile ->
        #   boto3.Session(profile_name="profile dev").resource
        self._client = boto3.Session().resource(
            "s3", config=Config(signature_version=UNSIGNED) if anonymous else None
        )

        # sanitise prefix to remove leading / if there is one
        self._prefix = AwsBucketBlobStorage._sanitise(namespace)
        self._anonymous = anonymous

    @staticmethod
    def _init_env(creds_name: Optional[str]):
        if "AWS_ACCESS_KEY_ID" not in os.environ or "AWS_SECRET_ACCESS_KEY" not in os.environ:
            # For EC2 instances we can run without os.env or a credential file if we have the
            # right IAM permissions
            # Bypass the no file found exception
            try:
                creds_file = FileLocator.find(
                    CURRENT_OR_HOME,
                    creds_name if creds_name else _DEFAULT_CREDS_FILE,
                )
                if creds_file:
                    os.environ[_ENV_AWS_CREDS] = str(creds_file.absolute())
                    logger.info(f"Reading credentials file from: {os.environ[_ENV_AWS_CREDS]}")
            # Do nothing if file not found
            except OSError:
                logger.info("Reading credentials from Instance metadata service on Amazon")
        else:
            logger.info("Reading credentials from environment variables")

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

    def _get_blob(self, key: Key) -> Object:
        namespaced_key = (
            f"{self._prefix}/{AwsBucketBlobStorage._sanitise(key)}"
            if self._prefix
            else AwsBucketBlobStorage._sanitise(key)
        )
        if namespaced_key is None:
            raise ValueError
        return self._client.Object(self._bucket_name, namespaced_key)

    @instrument_timer
    def __iter__(
        self,
    ) -> Generator[Blob, None, None]:  # Needs testing specially for 1k+ files
        try:
            for obj in (
                self._client.Bucket(self._bucket_name)
                .objects.filter(Prefix=f"{self._prefix}/" if self._prefix else "")
                .all()
            ):  # we can probably do it with pathlib to check if its the base dir
                if obj.key != f"{self._prefix}/":
                    yield _AwsBlob(obj.Object(), client=self._client, namespace=self._prefix)

        except botocore.exceptions.ClientError as error:
            raise BlobStorageError(
                f"Error listing contents of bucket '{self._bucket_name}' "
            ) from error

    @instrument_timer
    def put(self, key: Key, data: IO[bytes]) -> None:
        try:
            blob = self._get_blob(key)
            blob.put(Body=data)
        except botocore.exceptions.ClientError as error:
            raise BlobStorageError(f"Error uploading data for key '{key}'") from error

    @contextlib.contextmanager
    def putter(self, key: Key) -> Generator[IO[bytes], None, None]:
        # again, no streaming support in python API so put data in a buffer
        buffer = io.BytesIO()
        yield buffer
        buffer.seek(0)
        self.put(key, buffer)

    def get(self, key: Key) -> Blob:
        try:
            blob = self._get_blob(key)
            blob.reload()
            return _AwsBlob(blob, client=self._client, namespace=self._prefix)

        except botocore.exceptions.ClientError as error:
            err_response = error.response.get("Error")
            if err_response is not None and err_response.get("Code") == "404":
                raise BlobNotFoundError(f"Blob for key '{key}' does not exist") from error
            raise BlobStorageError(f"Error getting data for key '{key}'") from error

    @property
    def storage_id(self) -> str:
        return (
            f"{self.__class__.__name__}[bucket_name='{self._bucket_name}', "
            f"namespace='{self._prefix}']"
        )

    def namespace(self, prefix: str) -> Self:
        sanitised = AwsBucketBlobStorage._sanitise(prefix)
        new_prefix = f"{self._prefix}/{sanitised}" if self._prefix else sanitised
        return self.__class__(
            bucket_name=self._bucket_name,
            namespace=new_prefix,
            anonymous=self._anonymous,
        )


class DeletableAwsBucketBlobStorage(AwsBucketBlobStorage, DeletableBlobStorage):
    """Extension of `AwsBucketBlobStorage` with delete funcionality"""

    @instrument_timer
    def delete(self, key: Key) -> None:
        try:
            blob = self._get_blob(key)
            blob.delete()
        except botocore.exceptions.ClientError as error:
            raise BlobStorageError(f"Error deleting blob with key '{key}'") from error

# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""Tests for aws blob storage implementation."""
import io
import os
import re
from typing import Type

import boto3
import pytest
from moto import mock_s3

from di_service_locator.feature_defs.aws.blob_storage import (
    AwsBucketBlobStorage,
    DeletableAwsBucketBlobStorage,
)
from di_service_locator.feature_defs.interfaces import (
    BlobNotFoundError,
    BlobStorage,
    DeletableBlobStorage,
)


@pytest.fixture(name="mock_s3")
def _create_server():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"

    try:
        mock = mock_s3()
        mock.start()

        try:
            conn = boto3.resource("s3", region_name="us-east-1")
            conn.create_bucket(Bucket="test_bucket")
            yield conn
        finally:
            mock.stop()

    finally:
        del os.environ["AWS_ACCESS_KEY_ID"]
        del os.environ["AWS_SECRET_ACCESS_KEY"]
        del os.environ["AWS_SECURITY_TOKEN"]
        del os.environ["AWS_SESSION_TOKEN"]


@pytest.fixture(
    name="aws_storage_type", params=[AwsBucketBlobStorage, DeletableAwsBucketBlobStorage]
)
def _storage_type(request):
    return request.param


@pytest.fixture(name="aws_blob_storage")
def _create_aws_storage(
    aws_storage_type: Type[AwsBucketBlobStorage], namespace: str
) -> BlobStorage:
    return aws_storage_type(
        bucket_name="test_bucket",
        namespace=namespace,
        anonymous=False,
    )


def test_put_and_get(mock_s3, aws_blob_storage: BlobStorage):
    """Test put and get objects"""
    test_content = b"some content"
    aws_blob_storage.put(key="testdata", data=io.BytesIO(test_content))

    result = aws_blob_storage.get(key="/testdata")
    assert str(result) == "_AwsBlob {key=/testdata}"
    with result.stream() as f:
        assert f.read() == test_content


def test_putter_and_get(mock_s3, aws_blob_storage: BlobStorage):
    """Test putter and get for objects"""
    test_content = b"some content"
    with aws_blob_storage.putter(key="testdata") as f:
        f.write(test_content)

    result = aws_blob_storage.get(key="/testdata")
    assert str(result) == "_AwsBlob {key=/testdata}"
    with result.stream() as f:
        assert f.read() == test_content


def test_list(mock_s3, aws_blob_storage: BlobStorage):
    """Test listing of objects"""
    # put some content into the store first
    keys = ["test1.txt", "/test2.txt", "test3", "folder/test4.txt", "/folder/test5.txt"]
    for key in keys:
        aws_blob_storage.put(key=key, data=io.BytesIO(b"content"))

    contents = list(aws_blob_storage)
    expected_keys = [
        "/test1.txt",
        "/test2.txt",
        "/test3",
        "/folder/test4.txt",
        "/folder/test5.txt",
    ]

    actual_keys = [blob.key for blob in contents]
    assert len(actual_keys) == len(expected_keys)
    for expected_key in expected_keys:
        assert expected_key in actual_keys

    for content in contents:
        with content.stream() as f:
            assert f.read() == b"content"


def test_get_non_existent(mock_s3, aws_blob_storage: BlobStorage):
    """Test proper failure when object does not exist"""
    with pytest.raises(BlobNotFoundError, match="Blob for key 'dummy' does not exist"):
        _ = aws_blob_storage.get(key="dummy")


def test_namespace_scope(mock_s3, aws_blob_storage: BlobStorage):
    """Test namespace scoping works as expected"""
    aws_blob_storage.put(key="toplevel", data=io.BytesIO(b"content"))
    namespaced = aws_blob_storage.namespace(prefix="folder1/folder2")
    namespaced.put(key="nested", data=io.BytesIO(b"content"))
    namespaced_blobs = list(namespaced)
    assert len(namespaced_blobs) == 1  # should only see nested content
    assert namespaced_blobs[0].key == "/nested"

    # check that top level can see both entries
    expected_keys = ["/toplevel", "/folder1/folder2/nested"]
    actual_keys = [blob.key for blob in aws_blob_storage]
    for key in expected_keys:
        assert key in actual_keys


def test_incomplete_prefix(mock_s3, aws_blob_storage: BlobStorage):
    """Test that nected prefixes works as expected"""
    aws_blob_storage.put(key="toplevel", data=io.BytesIO(b"content"))
    namespaced = aws_blob_storage.namespace(prefix="top")
    namespaced.put(key="nested", data=io.BytesIO(b"content"))
    namespaced_blobs = list(namespaced)
    assert len(namespaced_blobs) == 1  # should only see nested content
    assert namespaced_blobs[0].key == "/nested"

    # check that top level can see both entries
    expected_keys = ["/toplevel", "/top/nested"]
    actual_keys = [blob.key for blob in aws_blob_storage]
    for key in expected_keys:
        assert key in actual_keys


@pytest.mark.parametrize("test_input, expected", [(b"some content", b"some content updated")])
def test_overwrite_blob(
    mock_s3,
    aws_blob_storage: BlobStorage,
    test_input: bytes,
    expected: bytes,
):
    """Test overwriting blobs works"""
    aws_blob_storage.put(key="testdata", data=io.BytesIO(test_input))
    aws_blob_storage.put(key="testdata", data=io.BytesIO(test_input + b" updated"))
    result = aws_blob_storage.get(key="/testdata")
    with result.stream() as f:
        # compare as decoded strings
        assert f.read().decode("utf-8") == expected.decode("utf-8")


@pytest.mark.parametrize(
    "aws_storage_type, expected_name",
    [
        [AwsBucketBlobStorage, "AwsBucketBlobStorage"],
        [DeletableAwsBucketBlobStorage, "DeletableAwsBucketBlobStorage"],
    ],
    indirect=["aws_storage_type"],
)
def test_storage_id(aws_blob_storage: BlobStorage, expected_name: str):
    """Test storage IDs are correct"""
    reg = rf"{expected_name}\[bucket_name='test_bucket', namespace='(.*)'\]"
    assert re.match(reg, aws_blob_storage.storage_id)


def test_stream_put_and_get(mock_s3, aws_blob_storage: BlobStorage):
    """Test put and get with streams"""
    test_content = b"some content"
    aws_blob_storage.put(key="testdata", data=io.BytesIO(test_content))

    result = aws_blob_storage.get(key="/testdata")
    assert str(result) == "_AwsBlob {key=/testdata}"
    with result.stream() as f:
        assert f.read(5) == b"some "
        assert f.read(100) == b"content"


@pytest.mark.parametrize("aws_storage_type", [DeletableAwsBucketBlobStorage], indirect=True)
@pytest.mark.parametrize(
    "key",
    ["file.txt", "b/another.txt"],
)
def test_delete(mock_s3, aws_blob_storage: DeletableBlobStorage, key: str) -> None:
    """Test delete objects works"""
    test_content = b"some content"
    aws_blob_storage.put(key=key, data=io.BytesIO(test_content))
    aws_blob_storage.put(key="c/other.txt", data=io.BytesIO(test_content))

    assert len(list(aws_blob_storage)) == 2
    aws_blob_storage.delete(key)
    assert len(list(aws_blob_storage)) == 1
    assert "/c/other.txt" in [obj.key for obj in aws_blob_storage]


@pytest.mark.parametrize("aws_storage_type", [DeletableAwsBucketBlobStorage], indirect=True)
@pytest.mark.parametrize("key", ["file.txt", "b", "b/", "another.txt"])
def test_delete_nonexistent(mock_s3, aws_blob_storage: DeletableBlobStorage, key: str):
    """Test deleting non-existent objects does not raise errors"""
    test_content = b"some content"
    aws_blob_storage.put(key="b/another.txt", data=io.BytesIO(test_content))
    aws_blob_storage.delete(key)
    assert "/b/another.txt" in [obj.key for obj in aws_blob_storage]

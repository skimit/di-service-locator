# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""Tests for google blob storage implementation."""
import io
import os
import re

import pytest
from gcp_storage_emulator.server import create_server

from di_service_locator.feature_defs.gcp.blob_storage import GoogleBucketBlobStorage
from di_service_locator.feature_defs.interfaces import BlobNotFoundError, BlobStorage


@pytest.fixture(name="mock_google_storage_server")
def _create_server():
    server = create_server("localhost", 9023, in_memory=True, default_bucket="test_bucket")
    server.start()
    os.environ["STORAGE_EMULATOR_HOST"] = "http://localhost:9023"
    try:
        yield
    finally:
        del os.environ["STORAGE_EMULATOR_HOST"]
        server.stop()


@pytest.fixture(
    name="google_blob_storage",
    params=[None, "namespace", "/namespace", "double/namespace"],
)
def _create_google_storage(request) -> BlobStorage:
    return GoogleBucketBlobStorage(
        project_name="test",
        bucket_name="test_bucket",
        namespace=request.param,
        anonymous=True,
    )


def test_put_and_get(mock_google_storage_server, google_blob_storage: BlobStorage):
    """Test put and get"""
    test_content = b"some content"
    google_blob_storage.put(key="testdata", data=io.BytesIO(test_content))

    result = google_blob_storage.get(key="/testdata")
    assert str(result) == "_GoogleBlob {key=/testdata}"
    with result.stream() as f:
        assert f.read() == test_content


def test_putter_and_get(mock_google_storage_server, google_blob_storage: BlobStorage):
    """Test putter and get"""
    test_content = b"some content"
    with google_blob_storage.putter(key="testdata") as f:
        f.write(test_content)

    result = google_blob_storage.get(key="/testdata")
    assert str(result) == "_GoogleBlob {key=/testdata}"
    with result.stream() as f:
        assert f.read() == test_content


def test_list(mock_google_storage_server, google_blob_storage: BlobStorage):
    """Test listing"""
    # put some content into the store first
    keys = ["test1.txt", "/test2.txt", "test3", "folder/test4.txt", "/folder/test5.txt"]
    for key in keys:
        google_blob_storage.put(key=key, data=io.BytesIO(b"content"))

    contents = list(google_blob_storage)
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


def test_get_non_existent(mock_google_storage_server, google_blob_storage: BlobStorage):
    """Test get non-existent object raises expected error"""
    with pytest.raises(BlobNotFoundError, match="Blob for key 'dummy' does not exist"):
        _ = google_blob_storage.get(key="dummy")


def test_namespace_scope(mock_google_storage_server, google_blob_storage: BlobStorage):
    """Test namespace scoping works"""
    google_blob_storage.put(key="toplevel", data=io.BytesIO(b"content"))
    namespaced = google_blob_storage.namespace(prefix="folder1/folder2")
    namespaced.put(key="nested", data=io.BytesIO(b"content"))
    namespaced_blobs = list(namespaced)
    assert len(namespaced_blobs) == 1  # should only see nested content
    assert namespaced_blobs[0].key == "/nested"

    # check that top level can see both entries
    expected_keys = ["/toplevel", "/folder1/folder2/nested"]
    actual_keys = [blob.key for blob in google_blob_storage]
    for key in expected_keys:
        assert key in actual_keys


def test_incomplete_prefix(mock_google_storage_server, google_blob_storage: BlobStorage):
    """Test incomplete prefix works as expected"""
    google_blob_storage.put(key="toplevel", data=io.BytesIO(b"content"))
    namespaced = google_blob_storage.namespace(prefix="top")
    namespaced.put(key="nested", data=io.BytesIO(b"content"))
    namespaced_blobs = list(namespaced)
    assert len(namespaced_blobs) == 1  # should only see nested content
    assert namespaced_blobs[0].key == "/nested"

    # check that top level can see both entries
    expected_keys = ["/toplevel", "/top/nested"]
    actual_keys = [blob.key for blob in google_blob_storage]
    for key in expected_keys:
        assert key in actual_keys


@pytest.mark.parametrize("test_input, expected", [(b"some content", b"some content updated")])
def test_overwrite_blob(
    mock_google_storage_server,
    google_blob_storage: BlobStorage,
    test_input: bytes,
    expected: bytes,
):
    """Test objects can be overwritten"""
    google_blob_storage.put(key="testdata", data=io.BytesIO(test_input))
    google_blob_storage.put(key="testdata", data=io.BytesIO(test_input + b" updated"))
    result = google_blob_storage.get(key="/testdata")
    with result.stream() as f:
        # compare as decoded strings
        assert f.read().decode("utf-8") == expected.decode("utf-8")


def test_storage_id(google_blob_storage: BlobStorage):
    """Test that object IDs work as expected"""
    reg = (
        r"GoogleBucketBlobStorage\[project_name='test', bucket_name='test_bucket', "
        r"namespace='(.*)'\]"
    )
    assert re.match(reg, google_blob_storage.storage_id)

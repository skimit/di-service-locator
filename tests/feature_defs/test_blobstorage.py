# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""Explicit tests for `FileBlobStorage` implementation."""
import dataclasses
import io
import json
import tempfile
from pathlib import Path
from typing import Generator, Type

import pytest

from di_service_locator.feature_defs.blob_storage import (
    DeletableFileBlobStorage,
    FileBlobStorage,
)
from di_service_locator.feature_defs.interfaces import (
    BlobNotFoundError,
    BlobStorage,
    BlobStorageError,
    DeletableBlobStorage,
)
from di_service_locator.utils.transcoding import text_to_bytes_writer


@dataclasses.dataclass
class StorageDetails:
    """Storage details for testing"""

    root_path: str
    storage: BlobStorage


@pytest.fixture(name="file_storage_type", params=[FileBlobStorage, DeletableFileBlobStorage])
def _storage_type(request):
    return request.param


@pytest.fixture(name="temporary_storage")
def temporary_file_blobstorage(
    namespace: str, file_storage_type: Type[FileBlobStorage]
) -> Generator[StorageDetails, None, None]:
    """
    Fixture for creating test blob storage implementation.

    Parameterized to also test namespaced instances of the generated blob storage.
    """
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        root_path = tmp_dir_name if namespace is None else f"{tmp_dir_name}/{namespace}"
        storage: BlobStorage = file_storage_type(root_path=tmp_dir_name)
        if namespace:
            storage = storage.namespace(namespace)
        yield StorageDetails(root_path=root_path, storage=storage)


@pytest.fixture(name="temporary_storage_with_contents")
def temporary_file_blobstorage_with_contents(temporary_storage):
    """
    Creates a `FileBlobStorage` with content.

    Storage structure looks like;
        root
        ├── b
        │   └── another.txt
        └── file.txt
    """
    root_path = Path(temporary_storage.root_path)
    with (root_path / "file.txt").open(mode="wb") as f:
        f.write(b"contents")
    folder = root_path / "b"
    folder.mkdir()
    with (folder / "another.txt").open(mode="wb") as f:
        f.write(b"more contents")

    yield temporary_storage


def test_list(temporary_storage_with_contents):
    """Test listing works as expected"""
    blob_storage: BlobStorage = temporary_storage_with_contents.storage
    contents = list(blob_storage)
    assert len(contents) == 2
    entry1 = [b for b in contents if b.key == "/file.txt"][0]
    assert entry1.key == "/file.txt"
    with entry1.stream() as st:
        assert st.read() == b"contents"
    entry2 = [b for b in contents if b.key == "/b/another.txt"][0]
    assert entry2.key == "/b/another.txt"
    with entry2.stream() as st:
        assert st.read() == b"more contents"


@pytest.mark.parametrize(
    ["path"], [["file.txt"], ["a/file.txt"], ["/a/b/file.txt"], ["/file.txt"]]
)
def test_put(temporary_storage, path: str):
    """Test put objects works as expected"""
    blob_storage: BlobStorage = temporary_storage.storage
    blob_storage.put(key=path, data=io.BytesIO(b"contents"))

    expected_file = Path(temporary_storage.root_path) / (
        path[1:] if path.startswith("/") else path
    )
    assert expected_file.exists()
    assert expected_file.is_file()
    with expected_file.open(mode="rb") as f:
        contents = f.read()
        assert contents == b"contents"


def test_get(temporary_storage_with_contents):
    """Test get objects works as expected"""
    blob_storage: BlobStorage = temporary_storage_with_contents.storage
    blob = blob_storage.get("b/another.txt")
    assert blob
    assert blob.key == "/b/another.txt"
    with blob.stream() as st:
        assert st.read() == b"more contents"


def test_get_non_existent(temporary_storage):
    """Test that getting non-existend object raises expected error"""
    blob_storage: BlobStorage = temporary_storage.storage
    with pytest.raises(BlobNotFoundError, match="Blob for key 'b/another.txt' does not exist"):
        _ = blob_storage.get("b/another.txt")


def test_get_invalid_key(temporary_storage):
    """Test that get with invalid key raises expected error"""
    blob_storage: BlobStorage = temporary_storage.storage
    with pytest.raises(BlobStorageError, match="Invalid key '../../outside_storage.err'"):
        _ = blob_storage.get("../../outside_storage.err")


def test_put_invalid_key(temporary_storage):
    """Test that put with invalid key raises expected error"""
    blob_storage: BlobStorage = temporary_storage.storage
    with pytest.raises(BlobStorageError, match="Invalid key '../../outside_storage.err'"):
        _ = blob_storage.put(key="../../outside_storage.err", data=io.BytesIO(b"abcde"))


def test_putter_invalid_key(temporary_storage):
    """Test that putter with invalid key raises expected error"""
    blob_storage: BlobStorage = temporary_storage.storage
    with pytest.raises(BlobStorageError, match="Invalid key '../../outside_storage.err'"):
        with blob_storage.putter(key="../../outside_storage.err") as _:
            pass


def test_namespace_invalid_prefix(temporary_storage):
    """Test that a namespace with invalid prefix riases the expected error"""
    blob_storage: BlobStorage = temporary_storage.storage
    with pytest.raises(BlobStorageError, match="Invalid key '../../outside_storage.err'"):
        _ = blob_storage.namespace(prefix="../../outside_storage.err")


@pytest.mark.parametrize(
    ["path"], [["file.txt"], ["a/file.txt"], ["/a/b/file.txt"], ["/file.txt"]]
)
def test_putter(temporary_storage, path: str):
    """Test that putter works as expected"""
    blob_storage: BlobStorage = temporary_storage.storage
    with blob_storage.putter(key=path) as stream:
        json.dump({"key": 5}, text_to_bytes_writer(stream))

    expected_file = Path(temporary_storage.root_path) / (
        path[1:] if path.startswith("/") else path
    )
    assert expected_file.exists()
    assert expected_file.is_file()
    with expected_file.open(mode="r") as file_stream:
        contents = file_stream.read()
        assert contents == '{"key": 5}'


def test_namespace_scope(temporary_storage):
    """Test that namespace scoping works as expected"""
    blob_storage: BlobStorage = temporary_storage.storage
    blob_storage.put(key="toplevel", data=io.BytesIO(b"content"))
    namespaced = blob_storage.namespace(prefix="folder1/folder2")
    namespaced.put(key="nested", data=io.BytesIO(b"content"))
    namespaced_blobs = list(namespaced)
    assert len(namespaced_blobs) == 1  # should only see nested content
    assert namespaced_blobs[0].key == "/nested"

    # check that top level can see both entries
    expected_keys = ["/toplevel", "/folder1/folder2/nested"]
    actual_keys = [blob.key for blob in blob_storage]
    for key in expected_keys:
        assert key in actual_keys


@pytest.mark.parametrize("file_storage_type", [DeletableFileBlobStorage], indirect=True)
@pytest.mark.parametrize("key", ["/file.txt", "/b/another.txt"])
def test_delete(temporary_storage_with_contents, key: str):
    """Test that delete works as expected"""
    blob_storage: DeletableBlobStorage = temporary_storage_with_contents.storage
    assert len(list(blob_storage)) == 2
    blob_storage.delete(key)
    assert len(list(blob_storage)) == 1
    assert key not in [obj.key for obj in blob_storage]


@pytest.mark.parametrize("file_storage_type", [DeletableFileBlobStorage], indirect=True)
@pytest.mark.parametrize("key", ["other.txt", "b", "b/", "another.txt"])
def test_delete_nonexistent(temporary_storage_with_contents, key: str):
    """Test that delete with non-existent object does not error"""
    blob_storage: DeletableBlobStorage = temporary_storage_with_contents.storage
    keys = [obj.key for obj in blob_storage]
    blob_storage.delete(key)
    assert keys == [obj.key for obj in blob_storage]

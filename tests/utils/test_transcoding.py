# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""Tests for transcoding functions."""
import json
import tempfile
from pathlib import Path

from di_service_locator.utils.transcoding import bytes_to_text_reader, text_to_bytes_writer


def test_text_to_bytes_writer():
    """Test text to bytes writer works as expected"""
    with tempfile.TemporaryDirectory() as temp_dir:
        file = Path(temp_dir) / "test.json"
        with file.open("wb") as f:
            # json wants to dump strings but we only have a byte stream
            # so...convert it on the way through!
            json.dump({"key": 5}, text_to_bytes_writer(f))
        with file.open("r") as f:
            # assert that the contents was written correctly
            assert f.read() == '{"key": 5}'


def test_bytes_to_text_reader():
    """Test bytes to text reader works as expected"""
    with tempfile.TemporaryDirectory() as temp_dir:
        file = Path(temp_dir) / "test.json"
        with file.open("w") as f:
            # write some test data to a file
            f.write("hello world")
        # open the file in binary mode
        with file.open("rb") as f:
            # convert the byte stream to text on the fly and check the contents as a string
            assert bytes_to_text_reader(f).read() == "hello world"

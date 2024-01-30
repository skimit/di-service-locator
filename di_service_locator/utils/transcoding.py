# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""Module containing useful utility functions to transcode streams on the fly."""
import codecs
from typing import IO, cast


def text_to_bytes_writer(byte_stream: IO[bytes], encoding: str = "utf-8") -> IO[str]:
    """
    Transcode text to bytes whilst writing.

    Makes a byte stream look like a text stream and handles encoding on the fly (utf-8).

    :param byte_stream: a byte stream to wrap
    :type byte_stream: IO[bytes]
    :param encoding: the encoding to use in the conversion, defaults to "utf-8"
    :type encoding: str, optional
    :return: the text stream that text can be written to
    :rtype: IO[str]
    """
    return cast(IO[str], codecs.getwriter(encoding)(byte_stream))


def bytes_to_text_reader(byte_stream: IO[bytes], encoding: str = "utf-8") -> IO[str]:
    """
    Transcode bytes to text whilst reading.

    Turn a byte stream into a text stream handling encoding on the fly (utf-8)

    :param byte_stream: a byte stream to convert
    :type stream_in: IO[bytes]
    :param encoding: the encoding to use for the conversion, defaults to "utf-8"
    :type encoding: str, optional
    :return: the text stream that can be read from
    :rtype: IO[str]
    """
    return cast(IO[str], codecs.getreader(encoding)(byte_stream))

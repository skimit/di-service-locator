# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""Generic useful stuff."""


def flatten_dict(a_dict, separator=".", prefix=""):
    """Flatten a dict."""
    return (
        {
            prefix + separator + k if prefix else k: v
            for kk, vv in a_dict.items()
            for k, v in flatten_dict(vv, separator, kk).items()
        }
        if isinstance(a_dict, dict)
        else {prefix: a_dict}
    )

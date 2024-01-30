# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""Feature errors."""


class FeatureError(Exception):
    """Generic base class error for all feature errors."""


class FeatureNotFound(FeatureError):
    """Error raised when a requested feature cannot be found."""


class MultipleFeatureDefaults(FeatureError):
    """Error raised when multiple factory definitions are set as default for a feature."""


class InvalidReturnType(FeatureError):
    """Error raised when an unexpected type is returned."""

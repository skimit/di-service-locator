# -=- encoding: utf-8 -=-
#
# Copyright (c) 2024 Deeper Insights. Subject to the MIT license.

"""Tests for config functions and property resolution."""
import os
import sys
from unittest.mock import patch

import pytest

from di_service_locator.config import STANDARD_PROPERTY_RESOLVER, FeatureConfigError
from di_service_locator.definitions import FactoryDefinition


@pytest.fixture(name="mock_factory_definition")
def _mock_factory_definition():
    return FactoryDefinition(
        fqn_impl_factory="dummy",
        fqn_interface="dummy",
        args=[1, "$PROPERTY1", 3],
        kwargs={"key": "value", "key2": "$PROPERTY2", "key3": "$PROPERTY3=default_value"},
    )


def test_property_resolver__args(mock_factory_definition):
    """Test that properties can be extracted from command line args."""
    testargs = ["--PROPERTY1=testvalue1", "--PROPERTY2=testvalue2"]
    with patch.object(sys, "argv", testargs):
        result = STANDARD_PROPERTY_RESOLVER.resolve(mock_factory_definition)
        assert result.args == [1, "testvalue1", 3]
        assert result.kwargs == {"key": "value", "key2": "testvalue2", "key3": "default_value"}


def test_property_resolver__env(mock_factory_definition):
    """Test that properties can be extracted from environment variables."""
    os.environ["PROPERTY1"] = "envtestvalue1"
    os.environ["PROPERTY2"] = "envtestvalue2"
    try:
        result = STANDARD_PROPERTY_RESOLVER.resolve(mock_factory_definition)
        assert result.args == [1, "envtestvalue1", 3]
        assert result.kwargs == {
            "key": "value",
            "key2": "envtestvalue2",
            "key3": "default_value",
        }
    finally:
        del os.environ["PROPERTY1"]
        del os.environ["PROPERTY2"]


def test_property_resolver__precedence(mock_factory_definition):
    """Test the properties are resolved in the correct order."""
    os.environ["PROPERTY1"] = "notused1"
    os.environ["PROPERTY2"] = "envtestvalue2"
    try:
        testargs = ["--PROPERTY1=testvalue1"]
        with patch.object(sys, "argv", testargs):
            result = STANDARD_PROPERTY_RESOLVER.resolve(mock_factory_definition)
            assert result.args == [1, "testvalue1", 3]
            assert result.kwargs == {
                "key": "value",
                "key2": "envtestvalue2",
                "key3": "default_value",
            }
    finally:
        del os.environ["PROPERTY1"]
        del os.environ["PROPERTY2"]


def test_property_resolver__not_found(mock_factory_definition):
    """Test that an error is thrown if property values cannot be found."""
    with pytest.raises(FeatureConfigError, match=r"No property value found for \$PROPERTY1"):
        _ = STANDARD_PROPERTY_RESOLVER.resolve(mock_factory_definition)
